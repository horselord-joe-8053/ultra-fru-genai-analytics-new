"""
Run schema + load_data via Cloud Run Job. Internal to setup_database.py.

Builds db-setup image, creates/updates job, executes, waits, verifies record count.
Used when Cloud SQL is private-IP-only and setup must run from inside GCP (VPC access).

Reference data: core_app/data/raw/fridge_sales_with_rating.csv
"""
import os
import re
import subprocess
import time
from datetime import datetime

from tools.cloud_shared.deploy.setup_database_utils import get_csv_path, get_repo_root
from tools.cloud_shared.logging import logger
from tools.cloud_shared.retry.with_heartbeat import poll_until, sleep_with_heartbeat
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

from .config import get_job_config
from .job_client import (
    create_or_update_job,
    execute_job,
    get_execution_status,
)

# How often to fetch container logs during heartbeat (seconds). Heartbeat runs every 15s.
# Must be <= job runtime so at least one fetch occurs; 15s ensures first heartbeat shows logs.
LOG_FETCH_INTERVAL_SEC = 15


def build_and_push_image(image_url: str) -> str:
    """Build and push db-setup image. Uses image_url from get_job_config to avoid redundant tofu init."""
    repo_root = get_repo_root()
    registry_host = image_url.split("/")[0]

    logger.info("Configuring Docker for Artifact Registry...")
    subprocess.run(
        ["gcloud", "auth", "configure-docker", registry_host, "--quiet"],
        check=True,
        capture_output=True,
    )

    dockerfile = os.path.join(repo_root, "tools", "gcp", "scope_shared", "deploy", "db_setup", "Dockerfile")
    if not os.path.exists(dockerfile):
        raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")

    logger.info("Building db-setup image (linux/amd64 for Cloud Run)...")
    subprocess.run(
        ["docker", "build", "--platform", "linux/amd64", "-f", dockerfile, "-t", image_url, repo_root],
        check=True,
        cwd=repo_root,
    )

    logger.info("Pushing db-setup image...")
    subprocess.run(["docker", "push", image_url], check=True, cwd=repo_root)
    return image_url


def run_schema_via_cloud_job(env: str, region: str, force: bool = False) -> dict:
    """
    Run schema + load_data via Cloud Run Job (private-IP Cloud SQL).
    Builds image, creates/updates job, executes, waits with heartbeat.
    Idempotent: load_data skips if data exists unless force=True.
    """
    logger.step("Running schema + load_data via Cloud Run Job (private-IP Cloud SQL)")

    cfg = get_job_config(env, region, force=force)
    job_name = cfg["job_name"]
    project_id = cfg["project_id"]

    # Build and push image (pass image from cfg to avoid redundant tofu init)
    with logger.Heartbeat("Building and pushing db-setup image"):
        build_and_push_image(cfg["image"])

    # Create or update job (always update so FRU_FORCE_REFRESH_DATA is correct for this run)
    logger.step(f"Creating/updating job {job_name}...")
    create_or_update_job(
        job_name=job_name,
        image=cfg["image"],
        region=region,
        project_id=project_id,
        vpc_connector_id=cfg["vpc_connector_id"],
        env_vars=cfg["env_vars"],
        secret_ids=cfg["secret_ids"],
    )
    logger.success(f"Job {job_name} ready")

    # Execute and wait (gcloud blocks until execution is accepted; cold start can take 1–2 min)
    logger.step(f"Executing job {job_name}...")
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
            err = f"Schema setup job failed: {failure_msg}" if failure_msg else "Schema setup job failed; check Cloud Run logs"
            raise RuntimeError(err)
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
            if new_lines:
                primary_cmd = f"gcloud run jobs logs read {job_name} --region={region} --project={project_id}"
                header = format_container_log_header(primary_cmd, len(new_lines))
                formatted = format_container_log_block(new_lines, header)
                return f"[heartbeat] Schema job running (elapsed: {elapsed}s)\n{formatted}"
        return f"[heartbeat] Schema job running (elapsed: {elapsed}s)"

    # Single heartbeat via poll_until (no logger.Heartbeat wrapper to avoid duplicate lines)
    try:
        ok = poll_until(
            check_done,
            timeout_sec=900,
            check_interval_sec=5,
            heartbeat_interval_sec=15,
            heartbeat_message_fn=heartbeat_fn,
        )
        if not ok:
            _print_job_logs_on_failure(project_id, region, job_name, "timed out (900s)", execution_name)
            raise RuntimeError("Schema + load_data job timed out")
    except RuntimeError as e:
        if "Schema setup job failed" in str(e):
            logger.error(str(e))
            _print_job_logs_on_failure(project_id, region, job_name, "failed", execution_name)
        raise
    # Job completed successfully; show container logs (heartbeat may have exited before first fetch for fast jobs)
    _print_container_logs_on_success(project_id, region, job_name, execution_start_time)
    logger.success("Schema + load_data completed via Cloud Run Job")
    return cfg


def _get_expected_count() -> int:
    """Expected fru_sales_embeddings count from CSV (core_app/data/raw/fridge_sales_with_rating.csv)."""
    csv_path = get_csv_path()
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    with open(csv_path) as f:
        return max(0, sum(1 for _ in f) - 1)


def _print_container_logs_on_success(
    project_id: str, region: str, job_name: str, execution_start_time: datetime
) -> None:
    """Fetch and display container logs after successful job completion (fast jobs may skip heartbeat)."""
    sleep_with_heartbeat(3, "Waiting for log propagation")
    logs = fetch_job_logs(
        project_id, region, job_name,
        freshness_min=15,
        log_start_time=execution_start_time,
    )
    all_lines = [l.strip() for l in logs.splitlines() if l.strip()]
    container_lines = filter_container_lines_with_timestamps(all_lines)
    if container_lines:
        primary_cmd = f"gcloud run jobs logs read {job_name} --region={region} --project={project_id}"
        header = format_container_log_header(primary_cmd, len(container_lines))
        logger.info(f"  {CONTAINER_LOG_GRAY}{header}{CONTAINER_LOG_RESET}")
        for line in container_lines:
            logger.info(format_container_log_line(line))


def _print_job_logs_on_failure(
    project_id: str, region: str, job_name: str, reason: str, execution_name: str | None = None
) -> None:
    """Fetch and print Cloud Run Job container logs when the job fails, to aid debugging."""
    logger.error(f"Schema job {reason}. Fetching container logs...")
    sleep_with_heartbeat(3, "Waiting for log propagation")
    logs = fetch_job_logs(project_id, region, job_name, freshness_min=15)
    lines = [l.strip() for l in logs.splitlines() if l.strip()][:80]
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


def _parse_count_from_logs(log_text: str) -> int | None:
    """Parse FRU_EMBEDDINGS_COUNT=N from job output. Returns first match (most recent execution)."""
    m = re.search(r"FRU_EMBEDDINGS_COUNT=(\d+)", log_text)
    return int(m.group(1)) if m else None


def run_verify_only(env: str, region: str) -> bool:
    """
    Run a verify-only job (SELECT COUNT) to check if DB is already initialized.
    Fast path when full setup failed (e.g. timeout) but DB may have been set up previously.
    Returns True if count matches expected.
    """
    expected = _get_expected_count()
    logger.info(f"Verify-only: checking if fru_sales_embeddings has {expected} rows")
    cfg = get_job_config(env, region)
    env_vars = {**cfg["env_vars"], "FRU_VERIFY_ONLY": "true"}
    create_or_update_job(
        job_name=cfg["job_name"],
        image=cfg["image"],
        region=region,
        project_id=cfg["project_id"],
        vpc_connector_id=cfg["vpc_connector_id"],
        env_vars=env_vars,
        secret_ids=cfg["secret_ids"],
    )
    execution_name = execute_job(cfg["project_id"], region, cfg["job_name"])
    for _ in range(36):
        sleep_with_heartbeat(5, "Waiting for verify-only job")
        status, failure_msg = get_execution_status(cfg["project_id"], region, execution_name)
        if status == "SUCCEEDED":
            break
        if status == "FAILED":
            logger.warning(f"Verify-only job failed: {failure_msg}" if failure_msg else "Verify-only job failed")
            return False
    else:
        logger.warning("Verify-only job timed out")
        return False
    sleep_with_heartbeat(5, "Waiting for log propagation")
    logs = fetch_job_logs(cfg["project_id"], region, cfg["job_name"], freshness_min=5)
    count = _parse_count_from_logs(logs)
    if count == expected:
        logger.success(f"Verify-only OK: DB already initialized ({count} rows)")
        return True
    logger.warning(f"Verify-only: got {count} rows, expected {expected}")
    return False


def run_and_verify(env: str, region: str, force: bool = False) -> bool:
    """
    Run schema + load_data via Cloud Run Job, then verify record count from logs.

    Returns True if job succeeded and count matches expected; False otherwise.
    Used by both deploy (setup_database.py) and verify (verify_db_run_job.py).
    """
    expected = _get_expected_count()
    logger.info(f"Expected fru_sales_embeddings count: {expected}")

    cfg = run_schema_via_cloud_job(env, region, force=force)
    project_id = cfg["project_id"]
    job_name = cfg["job_name"]

    # Fetch logs (allow time for propagation)
    logger.step("Fetching job logs for verification...")
    sleep_with_heartbeat(5, "Waiting for log propagation")

    count = None
    for attempt in range(5):
        logs = fetch_job_logs(project_id, region, job_name)
        log_lines = len([l for l in logs.splitlines() if l.strip()]) if logs else 0
        logger.info(f"Fetched {log_lines} log lines from job {job_name}")
        count = _parse_count_from_logs(logs)
        logger.info(f"Parsed FRU_EMBEDDINGS_COUNT={count} from logs")
        if count is not None:
            break
        logger.info(f"FRU_EMBEDDINGS_COUNT not found in logs (attempt {attempt + 1}/5)")
        sleep_with_heartbeat(10, "Retrying log fetch")

    if count is None:
        logger.error("Could not parse FRU_EMBEDDINGS_COUNT from job logs")
        return False

    if count == expected:
        logger.success(f"Verify OK: fru_sales_embeddings has {count} rows (expected {expected})")
        return True
    logger.error(f"Verify FAIL: got {count} rows, expected {expected}")
    return False
