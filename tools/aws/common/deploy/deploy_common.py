"""
Shared deploy helpers: tofu init/apply/output, S3/CSV, ECS bootstrap.
Used by deploy.py, deploy_kube.py, deploy_nonkube.py.
"""
import json
import os
import subprocess

from tools.cloud_shared.env import load_dotenv, require
from tools.aws.common.core.terra_runner import terra, terra_capture, get_terra_env
from tools.aws.common.core.backend import backend_config, resolve_region
from tools.cloud_shared.logging import logger
from tools.aws.terra_var_handling import get_base_vars
from tools.cloud_shared.retry import run_with_retry
from tools.aws.common.deploy.bootstrap_helpers import check_ecs_bootstrap_succeeded

load_dotenv()

ECS_NOT_IDEMPOTENT_MSG = "Creation of service was not idempotent"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
CSV_PATH = os.path.join(REPO_ROOT, "core_app", "data", "raw", "fridge_sales_with_rating.csv")


def upload_csv_to_delta_bucket(delta_bucket: str, region: str) -> bool:
    """Upload CSV to S3 raw/. Returns True if upload succeeded."""
    if not os.path.exists(CSV_PATH):
        logger.warning(f"CSV not found: {CSV_PATH}; Spark will use bundled CSV")
        return False
    s3_uri = f"s3://{delta_bucket}/raw/fridge_sales_with_rating.csv"
    logger.info(f"Uploading CSV to {s3_uri}")
    try:
        subprocess.run(
            ["aws", "s3", "cp", CSV_PATH, s3_uri, "--region", region],
            cwd=REPO_ROOT,
            check=True,
        )
        logger.success("CSV uploaded to S3")
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"CSV upload failed: {e}; Spark may fall back to bundled CSV")
        return False


def clear_delta_table(delta_bucket: str, region: str) -> None:
    """Clear existing Delta table in S3 so bootstrap creates fresh from CSV."""
    prefix = "delta/fru_sales/"
    s3_uri = f"s3://{delta_bucket}/{prefix}"
    logger.info(f"Clearing Delta table at {s3_uri}")
    try:
        subprocess.run(
            ["aws", "s3", "rm", s3_uri, "--recursive", "--region", region],
            cwd=REPO_ROOT,
            check=True,
        )
        logger.success("Delta table cleared")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Delta clear failed: {e}; bootstrap may upgrade existing table")


def init_stack(stack_dir: str, env: str, region: str | None = None) -> None:
    """Init stack with backend config."""
    logger.info(f"[INIT] {stack_dir}")
    cfg = backend_config(stack_dir, env, region)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe] + args
    run_with_retry(cmd, cwd=stack_dir, env=get_terra_env(region), description=f"tofu init in {stack_dir}")
    logger.success(f"[INIT OK] {stack_dir}")


def apply_stack(stack_dir: str, env: str, extra_vars: list[str], region: str | None = None) -> None:
    """Apply stack with base vars + extra vars."""
    logger.step(f"Applying stack: {stack_dir}")
    init_stack(stack_dir, env, region)
    get_base_vars(env, region)
    base: list[str] = []
    logger.info(f"[APPLY] Running tofu apply with base vars + extra vars: {extra_vars}")
    terra(["apply", "-auto-approve"] + base + extra_vars, cwd=stack_dir, check=True)
    logger.success(f"[APPLY OK] {stack_dir}")


def apply_stack_nonkube_with_ecs_import_retry(
    stack_dir: str, env: str, extra_vars: list[str], region: str | None = None
) -> None:
    """
    Apply nonkube stack. On ECS 'Creation of service was not idempotent' error,
    import the existing service into state and retry apply.
    """
    logger.step(f"Applying stack: {stack_dir}")
    init_stack(stack_dir, env, region)
    get_base_vars(env, region)
    prefix = os.getenv("FRU_PREFIX", "fru")
    cluster_name = f"{prefix}-{env}-ecs"
    service_name = f"{prefix}-{env}-api-svc"
    import_id = f"{cluster_name}/{service_name}"

    def _do_apply() -> subprocess.CompletedProcess:
        cmd = ["apply", "-auto-approve"] + extra_vars
        return terra_capture(cmd, cwd=stack_dir, region=region)

    result = _do_apply()
    if result.returncode == 0:
        logger.success(f"[APPLY OK] {stack_dir}")
        return

    # Print output so user sees the error
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=__import__("sys").stderr)

    if ECS_NOT_IDEMPOTENT_MSG not in (result.stderr or ""):
        raise subprocess.CalledProcessError(result.returncode, ["tofu", "apply"] + extra_vars)

    logger.warning(f"ECS service already exists; importing {import_id} into state and retrying...")
    import_result = terra_capture(
        ["import", "-lock=false", "module.ecs.aws_ecs_service.api", import_id],
        cwd=stack_dir,
        region=region,
    )
    if import_result.returncode != 0:
        if import_result.stderr:
            print(import_result.stderr, file=__import__("sys").stderr)
        raise subprocess.CalledProcessError(
            import_result.returncode,
            ["tofu", "import", "module.ecs.aws_ecs_service.api", import_id],
        )
    logger.success("ECS service imported into state")
    result2 = _do_apply()
    if result2.returncode != 0:
        if result2.stdout:
            print(result2.stdout)
        if result2.stderr:
            print(result2.stderr, file=__import__("sys").stderr)
        raise subprocess.CalledProcessError(result2.returncode, ["tofu", "apply"] + extra_vars)
    logger.success(f"[APPLY OK] {stack_dir}")


def tofu_output_json(stack_dir: str, env: str, region: str | None = None) -> dict:
    """Get tofu output as JSON."""
    logger.info(f"[OUTPUT] Getting outputs from {stack_dir}")
    init_stack(stack_dir, env, region)
    out = subprocess.check_output(
        [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
        cwd=stack_dir,
        text=True,
        env=get_terra_env(region),
    )
    logger.success(f"[OUTPUT OK] {stack_dir}")
    return json.loads(out)


def run_ecs_bootstrap(env: str, region: str | None = None, force: bool = False) -> None:
    """Run ECS one-off Spark task (run_analytics). Idempotent: skips if already succeeded."""
    region = region or os.getenv("CLOUD_REGION", "").strip() or require("AWS_REGION")

    if not force and check_ecs_bootstrap_succeeded(env):
        logger.success("[ECS BOOTSTRAP] Skip: bootstrap already succeeded (idempotent)")
        return

    logger.step("Executing ECS analytics bootstrap (Spark run_analytics)")
    out = tofu_output_json("live_deploy_aws/nonkube", env, region)
    cluster = out.get("ecs_cluster_name", {}).get("value") or f"{require('FRU_PREFIX')}-{env}-ecs"
    spark_task_def = out.get("spark_task_definition_arn", {}).get("value")
    if not spark_task_def:
        raise SystemExit("spark_task_definition_arn not in nonkube outputs")

    durable = tofu_output_json("live_deploy_aws/scope_shared/durable", env, region)
    private_subnets = durable.get("private_subnet_ids", {}).get("value", [])
    if not private_subnets:
        raise SystemExit("Could not determine private subnets for Spark bootstrap.")

    tasks_sg = out.get("ecs_tasks_sg_id", {}).get("value")
    if not tasks_sg:
        raise SystemExit("ecs_tasks_sg_id not in nonkube outputs")

    net_cfg = {
        "awsvpcConfiguration": {
            "subnets": private_subnets,
            "securityGroups": [tasks_sg],
            "assignPublicIp": "DISABLED",
        }
    }
    overrides = {
        "containerOverrides": [{
            "name": "spark",
            "command": [
                "/opt/spark/bin/spark-submit",
                "--packages", "io.delta:delta-spark_2.12:3.1.0,org.apache.hadoop:hadoop-aws:3.3.4",
                "/opt/fru/jobs/run_analytics.py",
            ],
        }]
    }

    logger.info("[ECS BOOTSTRAP] Starting one-off Spark task...")
    subprocess.run(
        [
            "aws", "ecs", "run-task",
            "--cluster", cluster,
            "--task-definition", spark_task_def,
            "--launch-type", "FARGATE",
            "--network-configuration", json.dumps(net_cfg),
            "--overrides", json.dumps(overrides),
            "--region", region,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    logger.success("ECS bootstrap task started successfully.")
