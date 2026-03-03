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
    target_first: str | None = None,
) -> None:
    """Init, plan, and apply stack with given vars.
    If target_first is set, plan first then apply that resource before full apply (fixes destroy-order)."""
    logger.step(f"Applying stack: {stack_dir}")
    init_stack(stack_dir, os.environ.get("FRU_ENV", "dev"), region)
    if target_first:
        terra(["plan", "-out=tfplan"] + plan_vars, cwd=stack_dir, check=True)
        logger.info(f"[APPLY] Targeted apply first: -target={target_first}")
        terra(["apply", "-auto-approve", f"-target={target_first}"] + plan_vars, cwd=stack_dir, check=False)
        terra(["apply", "-auto-approve"] + plan_vars, cwd=stack_dir, check=True)
    else:
        logger.info(f"[APPLY] Running tofu apply -auto-approve with plan_vars")
        terra(["apply", "-auto-approve"] + plan_vars, cwd=stack_dir, check=True)
    logger.success(f"[APPLY OK] {stack_dir}")


def apply_stack_with_plan(
    stack_dir: str,
    plan_vars: list[str],
    region: str | None = None,
    plan_file: str = "tfplan",
    target_first: str | None = None,
) -> None:
    """Apply using existing tfplan (run plan first, then apply tfplan).
    If target_first is set, apply that resource first to fix destroy-order issues (e.g. backend before NEG)."""
    logger.step(f"Applying stack (from {plan_file}): {stack_dir}")
    init_stack(stack_dir, os.environ.get("FRU_ENV", "dev"), region)
    if target_first:
        # Use vars (not plan file) so we only apply the backend update, not the NEG destroy
        logger.info(f"[APPLY] Targeted apply first: -target={target_first}")
        terra(["apply", "-auto-approve", f"-target={target_first}"] + plan_vars, cwd=stack_dir, check=False)
    # Apply the saved plan (or remainder)
    terra(["apply", "-auto-approve", plan_file], cwd=stack_dir, check=True)
    logger.success(f"[APPLY OK] {stack_dir}")


def run_deploy_stack(
    stack_path: str,
    plan_vars: list[str],
    region: str,
    env: str,
    apply: bool,
    apply_target_first: str | None = None,
) -> bool:
    """Init, plan, and optionally apply stack. Returns True if plan succeeded.
    If apply_target_first is set, apply that resource first (fixes FQDN<->IP migration destroy-order)."""
    init_stack(stack_path, env, region)
    result = terra(["plan", "-out=tfplan"] + plan_vars, cwd=stack_path, check=False)
    if apply and result.returncode == 0:
        apply_stack_with_plan(stack_path, plan_vars, region, target_first=apply_target_first)
    return result.returncode == 0


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
