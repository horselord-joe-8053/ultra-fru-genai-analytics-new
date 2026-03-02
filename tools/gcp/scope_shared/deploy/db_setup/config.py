"""
Configuration for db-setup Cloud Run Job. Kept separate from main deploy config.

Resolves job name, image URL, region, project from env and durable Terraform outputs.
Uses tofu output to read durable stack (Cloud SQL, VPC connector, secrets) without
coupling to the main IaC flow.
"""
import json
import os
import subprocess
from typing import Any

from tools.cloud_shared.deploy.setup_database_utils import get_repo_root

# Stack paths relative to repo root (durable has Cloud SQL + VPC connector)
_DURABLE_STACK_DIR = "infra_terraform/live_deploy/gcp/scope_shared/durable"
_NONDURABLE_STACK_DIR = "infra_terraform/live_deploy/gcp/scope_shared/nondurable"


def get_tofu_output_json(stack_dir: str, env: str, region: str, description: str = "tofu output") -> dict[str, Any]:
    """
    Get Terraform/OpenTofu outputs as JSON. Uses retry for transient failures (tofu init).
    stack_dir: path relative to repo root (e.g. infra_terraform/...).
    """
    from tools.cloud_shared.retry import run_with_retry
    from tools.gcp.scope_shared.core.backend import backend_config
    from tools.gcp.scope_shared.core.terra_runner import get_terra_env

    abs_stack = os.path.join(get_repo_root(), stack_dir) if not os.path.isabs(stack_dir) else stack_dir
    cfg = backend_config(abs_stack, env, region, cloud="gcp")
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    run_with_retry(
        [exe] + args,
        cwd=abs_stack,
        env=get_terra_env(region),
        description=f"tofu init for {description}",
    )
    out_raw = subprocess.check_output(
        [exe, "output", "-json"],
        cwd=abs_stack,
        text=True,
        env=get_terra_env(region),
    )
    return json.loads(out_raw)


def get_job_config(env: str, region: str, project_id: str | None = None, force: bool = False) -> dict[str, Any]:
    """
    Resolve job configuration from durable outputs and env.

    Returns dict with: job_name, image, region, project_id, vpc_connector_id,
    env_vars (PGHOST, PGPORT, FRU_CSV_PATH, FRU_FORCE_REFRESH_DATA, etc.),
    secret_ids (PGPASSWORD, OPENAI_API_KEY).
    """
    project = project_id or os.getenv("GCP_PROJECT_ID", "").strip()
    if not project:
        raise ValueError("GCP_PROJECT_ID required")

    # Read durable outputs for Cloud SQL + VPC connector + secrets
    out = get_tofu_output_json(_DURABLE_STACK_DIR, env, region, description="durable")

    private_ip = out.get("cloud_sql_private_ip", {}).get("value", "")
    db_name = out.get("cloud_sql_database_name", {}).get("value", "fru_db")
    vpc_connector_id = out.get("vpc_connector_id", {}).get("value", "")
    db_password_secret_id = out.get("db_password_plain_secret_id", {}).get("value", "")
    openai_secret_id = out.get("openai_api_key_secret_id", {}).get("value", "")

    if not private_ip:
        raise ValueError("cloud_sql_private_ip not in durable outputs; run durable apply first")
    if not vpc_connector_id:
        raise ValueError("vpc_connector_id not in durable outputs")
    if not db_password_secret_id:
        raise ValueError("db_password_plain_secret_id not in durable outputs")
    if not openai_secret_id:
        raise ValueError("openai_api_key_secret_id not in durable outputs; run durable_with_cooloff apply")

    from tools.gcp.scope_shared.core.resource_names import db_setup_job_name

    job_name = db_setup_job_name(env, region)

    # Image URL: use same Artifact Registry as app, with db-setup image name
    app_repo_url = _get_app_repo_url(env, region)
    image = f"{app_repo_url}/db-setup:latest"

    env_vars = {
        "PGHOST": private_ip,
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGDATABASE": db_name,
        "FRU_CSV_PATH": "/app/data/fridge_sales_with_rating.csv",
        "FRU_FORCE_REFRESH_DATA": "true" if force else "false",
    }

    secret_ids = {
        "PGPASSWORD": db_password_secret_id,
        "OPENAI_API_KEY": openai_secret_id,
    }

    return {
        "job_name": job_name,
        "image": image,
        "region": region,
        "project_id": project,
        "vpc_connector_id": vpc_connector_id,
        "env_vars": env_vars,
        "secret_ids": secret_ids,
    }


def _get_app_repo_url(env: str, region: str) -> str:
    """Get Artifact Registry app repo URL from nondurable stack."""
    out = get_tofu_output_json(_NONDURABLE_STACK_DIR, env, region, description="nondurable")
    url = out.get("artifact_registry_app_url", {}).get("value", "")
    if not url:
        raise ValueError("artifact_registry_app_url not in nondurable outputs")
    return url
