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


def init_stack(stack_dir: str, env: str, region: str | None = None) -> None:
    """Init stack with backend config. Idempotent; safe to call before destroy or output."""
    cfg = backend_config(stack_dir, env, region)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe] + args
    run_with_retry(cmd, cwd=stack_dir, env=get_terra_env(region), description=f"tofu init in {stack_dir}")
