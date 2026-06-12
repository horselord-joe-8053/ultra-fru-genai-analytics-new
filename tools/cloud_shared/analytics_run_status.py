"""
Read/write analytics batch job run status (singleton row in PostgreSQL).

Used by local scheduler (host) and API /analytics (container) so the UI can
surface stale snapshots and last Spark/scheduler errors.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

_MAX_ERROR_LEN = 500


def _db_config() -> Optional[Dict[str, Any]]:
    import os

    host = os.environ.get("PGHOST", "")
    password = os.environ.get("PGPASSWORD", "")
    if not host or not password:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": password,
        "dbname": os.environ.get("PGDATABASE", "fru_db"),
    }


def record_run_attempt(
    exit_code: int,
    error: Optional[str] = None,
    deploy_scope: Optional[str] = None,
) -> None:
    """Upsert last run attempt; on success clear last_error and set last_success_at."""
    cfg = _db_config()
    if not cfg:
        return

    import os

    import psycopg2

    now = datetime.now(timezone.utc)
    scope = deploy_scope or os.environ.get("DEPLOY_SCOPE", "nonkube")
    err = (error or "").strip()
    if err:
        err = err[-_MAX_ERROR_LEN:]

    try:
        conn = psycopg2.connect(**cfg)
        with conn.cursor() as cur:
            if exit_code == 0:
                cur.execute(
                    """
                    INSERT INTO analytics_run_status
                        (id, last_attempt_at, last_success_at, last_error, last_exit_code, deploy_scope)
                    VALUES (1, %s, %s, NULL, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        last_attempt_at = EXCLUDED.last_attempt_at,
                        last_success_at = EXCLUDED.last_success_at,
                        last_error = NULL,
                        last_exit_code = EXCLUDED.last_exit_code,
                        deploy_scope = EXCLUDED.deploy_scope
                    """,
                    (now, now, exit_code, scope),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO analytics_run_status
                        (id, last_attempt_at, last_success_at, last_error, last_exit_code, deploy_scope)
                    VALUES (1, %s, NULL, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        last_attempt_at = EXCLUDED.last_attempt_at,
                        last_error = EXCLUDED.last_error,
                        last_exit_code = EXCLUDED.last_exit_code,
                        deploy_scope = EXCLUDED.deploy_scope
                    """,
                    (now, err or f"Batch job failed (exit {exit_code})", exit_code, scope),
                )
        conn.commit()
        conn.close()
    except Exception:
        pass


def fetch_run_status() -> Optional[Dict[str, Any]]:
    """Return the singleton status row as a dict, or None if unavailable."""
    cfg = _db_config()
    if not cfg:
        return None

    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(**cfg)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT last_attempt_at, last_success_at, last_error, last_exit_code, deploy_scope
                FROM analytics_run_status
                WHERE id = 1
                """
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        out = dict(row)
        for key in ("last_attempt_at", "last_success_at"):
            if out.get(key) and hasattr(out[key], "isoformat"):
                dt = out[key]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                out[key] = dt.isoformat().replace("+00:00", "Z")
        return out
    except Exception:
        return None


def build_run_status_ui(
    batch_last_updated_at: Optional[datetime],
    interval_seconds: int,
    row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Derive UI-friendly stale/error messaging from DB status + snapshot age."""
    now = datetime.now(timezone.utc)
    interval_sec = max(60, int(interval_seconds or 180))
    stale_after_sec = int(interval_sec * 2.5)

    messages: list[str] = []
    severity = "ok"

    if batch_last_updated_at:
        if batch_last_updated_at.tzinfo is None:
            batch_last_updated_at = batch_last_updated_at.replace(tzinfo=timezone.utc)
        else:
            batch_last_updated_at = batch_last_updated_at.astimezone(timezone.utc)
        data_age_sec = (now - batch_last_updated_at).total_seconds()
        if data_age_sec > stale_after_sec:
            mins = max(1, int(data_age_sec // 60))
            messages.append(
                f"Snapshot is {mins} min old; batch jobs are scheduled every "
                f"{max(1, interval_sec // 60)} min."
            )
            severity = "warning"

    last_error = (row or {}).get("last_error")
    last_exit = (row or {}).get("last_exit_code")
    if last_error and last_exit not in (None, 0):
        messages.append(str(last_error))
        severity = "error"

    last_attempt = (row or {}).get("last_attempt_at")
    if last_attempt:
        try:
            attempt_dt = datetime.fromisoformat(
                str(last_attempt).replace("Z", "+00:00")
            )
            attempt_age = (now - attempt_dt).total_seconds()
            if attempt_age > stale_after_sec:
                messages.append(
                    "Background analytics scheduler may not be running "
                    "(no recent job attempts)."
                )
                if severity != "error":
                    severity = "warning"
        except (TypeError, ValueError):
            pass
    elif batch_last_updated_at:
        messages.append(
            "No scheduler run history in database; only the last successful snapshot is shown."
        )
        if severity != "error":
            severity = "warning"

    is_stale = severity in ("warning", "error")
    return {
        "last_attempt_at": (row or {}).get("last_attempt_at"),
        "last_success_at": (row or {}).get("last_success_at"),
        "last_error": last_error,
        "last_exit_code": last_exit,
        "deploy_scope": (row or {}).get("deploy_scope"),
        "is_stale": is_stale,
        "severity": severity,
        "status_message": " ".join(messages) if messages else None,
    }
