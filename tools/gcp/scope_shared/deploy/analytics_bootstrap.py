"""
GCP analytics bootstrap: one-off run of Spark job to populate batch_analytics.

Uses the same Cloud Run Job as periodic (spark_job); deploy runs it once via gcloud run jobs execute.
Ensures /analytics has meaningful data immediately after deploy (vs waiting for schedule).
Idempotent: skips if Cloud Logging shows "fru bootstrap success" in Spark logs.

Reference: tools/aws/scope_shared/deploy/deploy_common.run_ecs_bootstrap
"""
import os
import time
from datetime import datetime

from tools.cloud_shared.logging import logger
from tools.cloud_shared.retry.with_heartbeat import poll_until, sleep_with_heartbeat
from tools.gcp.scope_shared.core.resource_names import spark_job_name
from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json
from tools.gcp.scope_shared.deploy.db_setup.job_client import execute_job, get_execution_status
from tools.gcp.scope_shared.logging_special import (
    CONTAINER_LOG_GRAY,
    CONTAINER_LOG_RESET,
    fetch_job_logs,
    filter_container_lines_with_timestamps,
    filter_new_container_log_lines,
    format_container_log_block,
    format_container_log_header,
    format_container_log_line,
)

_NONDURABLE_STACK = "infra_terraform/live_deploy/gcp/scope_shared/nondurable"
_NONKUBE_STACK = "infra_terraform/live_deploy/gcp/nonkube"
BOOTSTRAP_SUCCESS_PATTERN = "fru bootstrap success"
BOOTSTRAP_TIMEOUT_SEC = 600  # Spark job can take 2–5 min
LOG_FETCH_INTERVAL_SEC = 15


def _check_bootstrap_succeeded_via_logs(env: str, region: str, project_id: str) -> bool:
    """Check Cloud Logging for bootstrap success. Returns True if pattern found."""
    try:
        import subprocess
        log_filter = (
            f'resource.type="cloud_run_job" '
            f'resource.labels.job_name="{spark_job_name(env, region)}" '
            f'textPayload=~"{BOOTSTRAP_SUCCESS_PATTERN}"'
        )
        result = subprocess.run(
            [
                "gcloud", "logging", "read", log_filter,
                "--project", project_id,
                "--limit", "5",
                "--format", "value(textPayload)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return BOOTSTRAP_SUCCESS_PATTERN in result.stdout
    except Exception as e:
        logger.warning(f"Could not check Cloud Logging for bootstrap success: {e}")
    return False


def _print_spark_logs_on_success(
    project_id: str, region: str, job_name: str, execution_start_time: datetime
) -> None:
    """Fetch and display Spark container logs after successful job completion."""
    sleep_with_heartbeat(3, "Waiting for log propagation")
    logs = fetch_job_logs(
        project_id, region, job_name,
        freshness_min=15,
        log_start_time=execution_start_time,
    )
    all_lines = [l.strip() for l in logs.splitlines() if l.strip()]
    container_lines = filter_container_lines_with_timestamps(all_lines)
    if not container_lines and all_lines:
        container_lines = all_lines[-30:]  # Spark uses plain print(); no bracketed timestamps
    if container_lines:
        primary_cmd = f"gcloud run jobs logs read {job_name} --region={region} --project={project_id}"
        header = format_container_log_header(primary_cmd, len(container_lines))
        logger.info(f"  {CONTAINER_LOG_GRAY}{header}{CONTAINER_LOG_RESET}")
        for line in container_lines:
            logger.info(format_container_log_line(line))


def _print_spark_logs_on_failure(
    project_id: str, region: str, job_name: str, reason: str
) -> None:
    """Fetch and print Spark container logs when the job fails, to aid debugging."""
    logger.error(f"Analytics bootstrap job {reason}. Fetching container logs...")
    sleep_with_heartbeat(3, "Waiting for log propagation")
    logs = fetch_job_logs(project_id, region, job_name, freshness_min=15)
    all_lines = [l.strip() for l in logs.splitlines() if l.strip()]
    lines = filter_container_lines_with_timestamps(all_lines) or all_lines[-80:]
    lines = lines[:80]
    if lines:
        primary_cmd = f"gcloud run jobs logs read {job_name} --region={region} --project={project_id}"
        header = format_container_log_header(primary_cmd, len(lines))
        logger.error(f"  {CONTAINER_LOG_GRAY}{header}{CONTAINER_LOG_RESET}")
        for line in lines:
            logger.error(format_container_log_line(line))
        logger.error(
            f"For full logs: gcloud run jobs logs read {job_name} --region={region} "
            f"--project={project_id} --limit=200"
        )
    else:
        logger.warning("No container logs found; check Cloud Console Logs Explorer")
        logger.warning(
            f"Try: gcloud run jobs logs read {job_name} --region={region} --project={project_id}"
        )


def run_analytics_bootstrap(env: str, region: str, force: bool = False) -> None:
    """
    Execute analytics bootstrap: run Spark job once (same job as periodic).
    Idempotent: skips if already succeeded (unless force=True).
    """
    if not force and _check_bootstrap_succeeded_via_logs(env, region, os.environ.get("GCP_PROJECT_ID", "")):
        logger.success("[ANALYTICS BOOTSTRAP] Skip: bootstrap already succeeded (idempotent)")
        return

    from tools.gcp.scope_shared.core.backend import resolve_region
    region = region or resolve_region(None)
    project_id = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project_id:
        raise SystemExit("GCP_PROJECT_ID must be set for analytics bootstrap")

    nonkube_out = get_tofu_output_json(_NONKUBE_STACK, env, region, description="nonkube")
    job_name = nonkube_out.get("spark_job_name", {}).get("value", "")
    if not job_name:
        job_name = spark_job_name(env, region)
        logger.info(f"spark_job_name not in outputs; using {job_name}")

    logger.step("Executing analytics bootstrap (Spark job, one-off)")
    t0 = time.time()
    execution_name = execute_job(project_id, region, job_name)
    wait_sec = int(time.time() - t0)
    logger.info(f"Execution started: {execution_name} (waited {wait_sec}s for Cloud Run to accept)")
    execution_start_time = datetime.utcnow()

    _container_log_last_timestamp: list[datetime | None] = [None]
    _last_fetch_elapsed: list[int] = [0]

    def check_done() -> bool:
        status, failure_msg = get_execution_status(project_id, region, execution_name)
        if status == "SUCCEEDED":
            return True
        if status == "FAILED":
            raise RuntimeError(
                f"Analytics bootstrap failed: {failure_msg}" if failure_msg else "Analytics bootstrap failed; check Cloud Run logs"
            )
        return False

    def heartbeat_fn(elapsed: int) -> str:
        if elapsed - _last_fetch_elapsed[0] >= LOG_FETCH_INTERVAL_SEC:
            _last_fetch_elapsed[0] = elapsed
            logs = fetch_job_logs(
                project_id, region, job_name,
                freshness_min=30,
                log_start_time=execution_start_time,
            )
            all_lines = [l.strip() for l in logs.splitlines() if l.strip()]
            new_lines = filter_new_container_log_lines(all_lines, _container_log_last_timestamp)
            # Spark uses plain print(); no bracketed timestamps. Fallback to last N lines.
            if not new_lines and all_lines:
                new_lines = all_lines[-15:]
            if new_lines:
                primary_cmd = f"gcloud run jobs logs read {job_name} --region={region} --project={project_id}"
                header = format_container_log_header(primary_cmd, len(new_lines))
                formatted = format_container_log_block(new_lines, header)
                return f"[heartbeat] Spark job running (elapsed: {elapsed}s)\n{formatted}"
        return f"[heartbeat] Spark job running (elapsed: {elapsed}s)"

    try:
        ok = poll_until(
            check_done,
            timeout_sec=BOOTSTRAP_TIMEOUT_SEC,
            check_interval_sec=10,
            heartbeat_interval_sec=15,
            heartbeat_message_fn=heartbeat_fn,
        )
        if not ok:
            _print_spark_logs_on_failure(project_id, region, job_name, "timed out")
            status, msg = get_execution_status(project_id, region, execution_name)
            raise SystemExit(f"Analytics bootstrap failed: {status} {msg}")
    except RuntimeError as e:
        if "Analytics bootstrap failed" in str(e):
            logger.error(str(e))
            _print_spark_logs_on_failure(project_id, region, job_name, "failed")
        raise SystemExit(str(e))

    _print_spark_logs_on_success(project_id, region, job_name, execution_start_time)
    logger.success("Analytics bootstrap complete (batch_analytics populated)")
