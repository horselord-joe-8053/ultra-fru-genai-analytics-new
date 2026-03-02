"""
gcloud wrappers for Cloud Run Job: create/update and execute.
Used by setup_database.py when running schema via Cloud Run Job.
Job may be created by Terraform (durable) or gcloud; gcloud deploy updates it.
"""
import json
import subprocess
import time
from typing import Any


def _get_project_number(project_id: str) -> str:
    """Resolve project number from project ID. Cloud Run secret paths require project number, not ID."""
    result = subprocess.run(
        ["gcloud", "projects", "describe", project_id, "--format", "value(projectNumber)"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Could not get project number for {project_id}: {result.stderr or result.stdout}")
    return result.stdout.strip()


def job_exists(project_id: str, region: str, job_name: str) -> bool:
    """Check if the Cloud Run Job exists."""
    try:
        subprocess.run(
            [
                "gcloud", "run", "jobs", "describe", job_name,
                "--region", region,
                "--project", project_id,
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def create_or_update_job(
    job_name: str,
    image: str,
    region: str,
    project_id: str,
    vpc_connector_id: str,
    env_vars: dict[str, str],
    secret_ids: dict[str, str],
) -> None:
    """
    Create or update the db-setup Cloud Run Job via gcloud.

    Uses --vpc-connector for private IP access to Cloud SQL.
    Env vars and secrets are passed to the container.
    """
    args = [
        "gcloud", "run", "jobs", "deploy", job_name,
        "--image", image,
        "--region", region,
        "--project", project_id,
        "--vpc-connector", vpc_connector_id,
        "--vpc-egress", "private-ranges-only",
        "--task-timeout", "600",
        "--command", "python,/app/run_schema_and_load.py",
    ]

    for k, v in env_vars.items():
        args.extend(["--set-env-vars", f"{k}={v}"])

    # Cloud Run API requires projects/PROJECT_NUMBER/secrets/NAME (not project ID)
    project_number = _get_project_number(project_id)
    for k, secret_id in secret_ids.items():
        secret_path = f"projects/{project_number}/secrets/{secret_id}:latest"
        args.extend(["--set-secrets", f"{k}={secret_path}"])

    subprocess.run(args, check=True, timeout=120)


def execute_job(project_id: str, region: str, job_name: str) -> str:
    """
    Execute the Cloud Run Job. Returns execution resource name for polling.

    Example: projects/PROJECT/locations/REGION/jobs/JOB/executions/EXEC_ID
    """
    result = subprocess.run(
        [
            "gcloud", "run", "jobs", "execute", job_name,
            "--region", region,
            "--project", project_id,
            "--format", "value(name)",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=150,
    )
    execution_name = result.stdout.strip()
    if not execution_name:
        raise RuntimeError("gcloud run jobs execute did not return execution name")
    return execution_name


def get_execution_status(project_id: str, region: str, execution_name: str) -> tuple[str, str]:
    """
    Get execution status: (RUNNING|SUCCEEDED|FAILED|UNKNOWN, message).
    Cloud Run Job emits a definite signal when done: conditions with state CONDITION_SUCCEEDED
    or CONDITION_FAILED. Also checks completionTime/succeededCount/failedCount as fallback.
    When FAILED, message contains the condition message (e.g. "Container called exit(2)").
    """
    out = subprocess.run(
        [
            "gcloud", "run", "jobs", "executions", "describe", execution_name,
            "--region", region,
            "--project", project_id,
            "--format", "json",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if out.returncode != 0:
        return "UNKNOWN", ""
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return "UNKNOWN", ""

    # Cloud Run: conditions and completion fields live under status (ExecutionStatus)
    status = data.get("status") or {}
    conditions = data.get("conditions", []) or status.get("conditions", [])
    for c in conditions:
        state = c.get("state", "")
        cond_status = c.get("status", "")  # v1: "True" | "False" | "Unknown"
        msg = c.get("message", "")
        if state == "CONDITION_SUCCEEDED":
            return "SUCCEEDED", msg
        if state == "CONDITION_FAILED":
            return "FAILED", msg
        # v1 API: type=Completed, status=True|False (or reason=Succeeded|Failed)
        if c.get("type") == "Completed":
            if cond_status == "True" or c.get("reason") == "Succeeded":
                return "SUCCEEDED", msg
            if cond_status == "False" or c.get("reason") == "Failed":
                return "FAILED", msg

    # Fallback: completionTime + succeededCount/failedCount (under status)
    completion_time = data.get("completionTime") or status.get("completionTime")
    task_count = data.get("taskCount") or status.get("taskCount") or 1
    succeeded = data.get("succeededCount", status.get("succeededCount", 0))
    failed = data.get("failedCount", status.get("failedCount", 0))

    if completion_time:
        if failed > 0:
            fail_msg = next((c.get("message", "") for c in conditions if c.get("message")), "Task failed")
            return "FAILED", fail_msg or "Task failed"
        if succeeded >= task_count and task_count > 0:
            return "SUCCEEDED", ""
        if succeeded >= 1:
            return "SUCCEEDED", ""

    # Single-task job: succeededCount=1 means done (even if completionTime not yet propagated)
    if task_count == 1 and succeeded >= 1 and failed == 0:
        return "SUCCEEDED", ""

    return "RUNNING", ""


def wait_for_execution(
    project_id: str,
    region: str,
    execution_name: str,
    poll_interval: int = 5,
    timeout_sec: int = 300,
) -> bool:
    """
    Poll until execution completes. Returns True if SUCCEEDED, False if FAILED or timeout.
    """
    start = time.time()
    while time.time() - start < timeout_sec:
        status, _ = get_execution_status(project_id, region, execution_name)
        if status == "SUCCEEDED":
            return True
        if status == "FAILED":
            return False
        time.sleep(poll_interval)
    return False
