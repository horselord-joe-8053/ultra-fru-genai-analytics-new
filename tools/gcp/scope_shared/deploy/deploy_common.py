"""
Shared deploy helpers for GCP: tofu init/apply/output.
Reference: tools/aws/scope_shared/deploy/deploy_common.py
"""
import os
import subprocess

from tools.gcp.scope_shared.core.terra_init import init_stack
from tools.gcp.scope_shared.core.terra_runner import terra, terra_capture, get_terra_env
from tools.cloud_shared.logging import logger


def apply_stack(
    stack_dir: str,
    plan_vars: list[str],
    region: str | None = None,
) -> None:
    """Init, plan, and apply stack with given vars."""
    logger.step(f"Applying stack: {stack_dir}")
    init_stack(stack_dir, os.environ.get("FRU_ENV", "dev"), region)
    logger.info(f"[APPLY] Running tofu apply -auto-approve with plan_vars")
    terra(["apply", "-auto-approve"] + plan_vars, cwd=stack_dir, check=True)
    logger.success(f"[APPLY OK] {stack_dir}")


def apply_stack_with_plan(
    stack_dir: str,
    plan_vars: list[str],
    region: str | None = None,
    plan_file: str = "tfplan",
) -> None:
    """Apply using existing tfplan (run plan first, then apply tfplan)."""
    logger.step(f"Applying stack (from {plan_file}): {stack_dir}")
    init_stack(stack_dir, os.environ.get("FRU_ENV", "dev"), region)
    # Apply the saved plan
    terra(["apply", "-auto-approve", plan_file], cwd=stack_dir, check=True)
    logger.success(f"[APPLY OK] {stack_dir}")


def plan_shows_no_changes(
    stack_dir: str,
    plan_vars: list[str],
    region: str | None = None,
) -> bool:
    """Run tofu plan -detailed-exitcode. Return True if no changes (exit 0)."""
    result = terra_capture(
        ["plan", "-detailed-exitcode"] + plan_vars,
        cwd=stack_dir,
        region=region,
    )
    return result.returncode == 0
