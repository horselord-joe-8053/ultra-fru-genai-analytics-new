"""
Save Spark analytics results to PostgreSQL batch_analytics table.
Standalone - no backend.* dependencies. Uses os.environ for config.

Note: batch_analytics is shared by both Kube (CronJob) and Nonkube (EventBridge) Spark jobs.
In PROD only one scope is deployed; in DEV both may run. See docs/learned/cloud_shared/ANALYTICS_AND_DATA.md.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    from analytics_logger import info as log_info, success as log_success, warning as log_warning, error as log_error
except ImportError:
    def _log(level: str):
        def _f(msg: str):
            print(f"[{level}] {msg}", flush=True)
        return _f
    log_info = _log("INFO")
    log_success = _log("SUCCESS")
    log_warning = _log("WARNING")
    log_error = _log("ERROR")


_MAX_RUN_ERROR_LEN = 500


def _db_config_from_env() -> Optional[Dict[str, Any]]:
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
    db_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Upsert analytics_run_status singleton (Spark CronJob/EventBridge path).

    Mirrors tools/cloud_shared/analytics_run_status.record_run_attempt so the
    Spark image (jobs-only) can write scheduler history without backend deps.
    """
    cfg = db_config or _db_config_from_env()
    if not cfg:
        return

    import psycopg2

    now = datetime.now(timezone.utc)
    scope = deploy_scope or os.environ.get("DEPLOY_SCOPE", "nonkube")
    err = (error or "").strip()
    if err:
        err = err[:_MAX_RUN_ERROR_LEN]

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
    except Exception as e:
        log_warning(f"Could not record analytics run status: {e}")


def save_analytics_to_db(
    sales_by_brand: list,
    store_performance: list,
    feedback_analysis: list,
    top_models: list,
    price_stats: Dict[str, Any],
    total_records: int,
    total_revenue: float,
    deploy_scope: Optional[str] = None,
    db_config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Save analytics results to PostgreSQL batch_analytics table.
    All data is stored as JSONB.
    """
    if db_config is None:
        db_config = {
            "host": os.environ.get("PGHOST", ""),
            "port": int(os.environ.get("PGPORT", "5432")),
            "user": os.environ.get("PGUSER", "postgres"),
            "password": os.environ.get("PGPASSWORD", ""),
            "dbname": os.environ.get("PGDATABASE", "fru_db"),
        }
    if not db_config.get("host") or not db_config.get("password"):
        log_warning("PGHOST and PGPASSWORD required for save_analytics_to_db; skipping")
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        scope_val = deploy_scope or os.environ.get("DEPLOY_SCOPE", "")
        cur.execute(
            """
            INSERT INTO batch_analytics
            (sales_by_brand, store_performance, feedback_analysis, top_models,
             price_stats, total_records, total_revenue, deploy_scope)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                json.dumps(sales_by_brand),
                json.dumps(store_performance),
                json.dumps(feedback_analysis),
                json.dumps(top_models),
                json.dumps(price_stats),
                total_records,
                total_revenue,
                scope_val or None,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        log_success("Analytics saved to database")
        record_run_attempt(0, deploy_scope=scope_val or None, db_config=db_config)
        return True
    except Exception as e:
        log_error(f"Error saving analytics to database: {e}")
        record_run_attempt(1, error=str(e), deploy_scope=deploy_scope, db_config=db_config)
        return False


def verify_saved_total_records(expected: int, db_config: Optional[Dict[str, Any]] = None) -> None:
    """
    ETL self-check: verify latest batch_analytics row has total_records == expected.
    Raises RuntimeError on mismatch. Replaces CloudWatch/Cloud Logging log scraping.
    """
    if db_config is None:
        db_config = {
            "host": os.environ.get("PGHOST", ""),
            "port": int(os.environ.get("PGPORT", "5432")),
            "user": os.environ.get("PGUSER", "postgres"),
            "password": os.environ.get("PGPASSWORD", ""),
            "dbname": os.environ.get("PGDATABASE", "fru_db"),
        }
    if not db_config.get("host") or not db_config.get("password"):
        raise RuntimeError("PGHOST and PGPASSWORD required for verify_saved_total_records")

    import psycopg2
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    cur.execute(
        "SELECT total_records FROM batch_analytics ORDER BY created_at DESC LIMIT 1"
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        raise RuntimeError("No batch_analytics row found after save")
    db_total = int(row[0])
    if db_total != expected:
        raise RuntimeError(
            f"ETL self-check failed: saved total_records={db_total} != expected={expected}"
        )
