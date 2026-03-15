"""
Shared Terraform/OpenTofu init logic for kube, nonkube, and shared stacks.

Used by teardown, deploy, verify, and pre-destroy flows.
"""
import os
import subprocess

from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.backend import backend_config
from tools.aws.scope_shared.core.terra_runner import get_terra_env
from tools.cloud_shared.retry import run_with_retry


def _resolve_stack_dir(stack_dir: str) -> str:
    """Resolve stack_dir to absolute path. Uses REPO_ROOT so cwd-independent."""
    if os.path.isabs(stack_dir):
        return stack_dir
    root = os.environ.get("REPO_ROOT") or os.getcwd()
    return os.path.abspath(os.path.join(root, stack_dir))


def init_stack(stack_dir: str, env: str, region: str | None = None) -> None:
    """Init stack with backend config. Idempotent; safe to call before destroy or output."""
    stack_abs = _resolve_stack_dir(stack_dir)
    cfg = backend_config(stack_dir, env, region)
    # Log deploy region; backend-config region= is S3 bucket location (may differ from deploy region)
    deploy_region = region or os.getenv("CLOUD_REGION", "")
    if deploy_region:
        logger.info(f"Init {stack_dir} (deploy region: {deploy_region})")
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe] + args
    run_with_retry(cmd, cwd=stack_abs, env=get_terra_env(region), description=f"tofu init in {stack_dir}")
