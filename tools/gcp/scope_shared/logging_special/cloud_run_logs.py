"""
Fetch and filter Cloud Run Job container logs.
Used by db-setup cloud_job and analytics bootstrap.
"""
import re
import subprocess
from datetime import datetime, timedelta

from tools.cloud_shared.logging import logger


def fetch_job_logs(
    project_id: str,
    region: str,
    job_name: str,
    freshness_min: int = 15,
    log_start_time: datetime | None = None,
) -> str:
    """
    Fetch recent Cloud Run Job container logs.
    When log_start_time is set, filter to logs from that time onward (scopes to current execution).
    """
    log_filter = ""
    if log_start_time is not None:
        ts = (log_start_time - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        log_filter = f'timestamp>="{ts}"'

    args = [
        "gcloud", "run", "jobs", "logs", "read", job_name,
        "--region", region,
        "--project", project_id,
        "--limit", "200",
        "--freshness", f"{freshness_min}m",
        "--format", "value(textPayload)",
    ]
    if log_filter:
        args.extend(["--log-filter", log_filter])
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and (result.stdout or "").strip():
        return result.stdout or ""

    filter_expr = (
        f'resource.type="cloud_run_job" '
        f'resource.labels.job_name="{job_name}" '
        f'resource.labels.location="{region}"'
    )
    if log_filter:
        filter_expr = f"({filter_expr}) AND {log_filter}"
    result = subprocess.run(
        [
            "gcloud", "logging", "read", filter_expr,
            "--project", project_id,
            "--format", "value(textPayload)",
            "--limit", "200",
            "--freshness", f"{freshness_min}m",
            "--order", "desc",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        logger.warning(f"gcloud logging read failed: {result.stderr}")
        return ""
    return result.stdout or ""


def filter_new_container_log_lines(
    lines: list[str],
    last_shown_timestamp_ref: list[datetime | None],
) -> list[str]:
    """
    Return container log lines with bracketed timestamps later than last_shown.
    Avoids repeating logs on each heartbeat. Updates last_shown_timestamp_ref[0].
    """
    # Timestamp is from our logger; allow any timezone suffix (UTC, AEST, etc.) or none
    BRACKETED_TS = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)[^\]]*\]", re.I)
    last = last_shown_timestamp_ref[0]

    def parse_ts(line: str) -> datetime | None:
        m = BRACKETED_TS.search(line.strip())
        if not m:
            return None
        try:
            return datetime.strptime(m.group(1)[:26], "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return None

    new_lines: list[str] = []
    max_ts = last

    for line in lines:
        ts = parse_ts(line)
        if ts is not None:
            if last is None or ts > last:
                new_lines.append(line)
                if max_ts is None or ts > max_ts:
                    max_ts = ts

    if new_lines:
        last_shown_timestamp_ref[0] = max_ts if max_ts is not None else datetime.min
    return new_lines


def filter_container_lines_with_timestamps(lines: list[str]) -> list[str]:
    """Filter to lines with bracketed timestamps (container stdout format)."""
    # Timestamp is from our logger; allow any timezone suffix (UTC, AEST, etc.) or none
    BRACKETED_TS = re.compile(r"\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+[^\]]*\]", re.I)
    return [l for l in lines if BRACKETED_TS.search(l)]
