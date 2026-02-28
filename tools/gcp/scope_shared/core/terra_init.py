"""Shared Terraform/OpenTofu init logic for GCP stacks (reference: tools/aws/scope_shared/core/terra_init.py)."""
import os

from tools.cloud_shared.logging import logger
from tools.gcp.scope_shared.core.backend import backend_config
from tools.gcp.scope_shared.core.terra_runner import get_terra_env
from tools.cloud_shared.retry import run_with_retry


def init_stack(stack_dir: str, env: str, region: str | None = None) -> None:
    """Init stack with GCS backend config."""
    cfg = backend_config(stack_dir, env, region, cloud="gcp")
    deploy_region = region or os.getenv("CLOUD_REGION", "")
    if deploy_region:
        logger.info(f"Init {stack_dir} (deploy region: {deploy_region})")
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe] + args
    run_with_retry(cmd, cwd=stack_dir, env=get_terra_env(region), description=f"tofu init in {stack_dir}")
