"""
Shared import logic for pre-existing AWS resources (import_preexist).

Pattern from legacy: orchestration/terraform/import_preexist/common/lib_import_common.sh
When resources exist in AWS but not in Terraform state (e.g. after brutal removal or
partial teardown), apply fails with EntityAlreadyExists. Import adopts them into state.

Safe to run always: non-existent resources are skipped; already-in-state returns OK.
"""
import os
import re
import subprocess

from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_runner import get_terra_env

# Patterns that mean "resource does not exist in AWS" - safe to skip
SKIP_PATTERNS = re.compile(
    r"Cannot import non-existent|NoSuchEntity|ResourceNotFoundException|"
    r"cannot be found|does not exist|NoSuchKey|NotFound",
    re.I,
)
# Patterns that mean "already in state" - success
ALREADY_MANAGED_PATTERNS = re.compile(
    r"already managed by Terraform|Resource already managed|Import (prepared|successful|complete)",
    re.I,
)


def _resolve_stack_dir(stack_dir: str) -> str:
    """Resolve stack_dir to absolute path (relative paths use cwd)."""
    if os.path.isabs(stack_dir):
        return stack_dir
    root = os.environ.get("REPO_ROOT") or os.getcwd()
    return os.path.abspath(os.path.join(root, stack_dir))


def import_one_resource(
    stack_dir: str,
    addr: str,
    resource_id: str,
    region: str | None = None,
    verbose: bool = False,
    allow_skip_nonexistent: bool = True,
    extra_env: dict | None = None,
) -> bool:
    """
    Run tofu import for one resource. Returns True on success or skip, False on failure.
    Idempotent: already-in-state and non-existent are treated as success.
    """
    cwd = _resolve_stack_dir(stack_dir)
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe, "import", "-lock=false", "-input=false", addr, resource_id]
    env = get_terra_env(region, extra=extra_env)
    if verbose:
        logger.info(f"  [import] cwd={cwd} cmd={' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )

    out = (result.stdout or "") + (result.stderr or "")
    if verbose and out.strip():
        for line in out.strip().split("\n"):
            logger.info(f"  [import out] {line}")

    if result.returncode == 0:
        if ALREADY_MANAGED_PATTERNS.search(out):
            logger.info(f"  OK (already in state—import skipped; harmless, not an error): {addr}")
        else:
            logger.success(f"  OK: {addr}")
        return True

    # returncode != 0: failure indicators take precedence over "already managed"
    if SKIP_PATTERNS.search(out):
        if allow_skip_nonexistent:
            logger.info(f"  Skip (resource does not exist in AWS): {addr}")
            return True
        logger.warning(f"  Import failed (provider cannot find resource): {addr}")
        err_text = (result.stderr or result.stdout or "").strip()
        for line in err_text.split("\n")[-12:]:
            if line.strip():
                logger.info(f"    {line}")
        return False

    if ALREADY_MANAGED_PATTERNS.search(out):
        logger.info(f"  OK (already in state—import skipped; harmless, not an error): {addr}")
        return True

    logger.warning(f"  Import failed: {addr}")
    err_text = (result.stderr or result.stdout or "").strip()
    for line in err_text.split("\n")[-12:]:
        if line.strip():
            logger.info(f"    {line}")
    return False


def state_contains(stack_dir: str, addr: str, region: str | None = None) -> bool:
    """Check if resource addr exists in Terraform state."""
    cwd = _resolve_stack_dir(stack_dir)
    exe = os.getenv("FRU_TF_BIN", "tofu")
    result = subprocess.run(
        [exe, "state", "list"],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=get_terra_env(region),
    )
    if result.returncode != 0:
        return False
    return addr in (result.stdout or "")


def sg_rule_import_id(
    security_group_id: str,
    rule_type: str,
    protocol: str,
    from_port: int,
    to_port: int,
    source_security_group_id: str,
) -> str:
    """
    Build Terraform import ID for aws_security_group_rule (ingress from another SG).
    Format: sg_id_type_protocol_from_to_source_sg
    """
    return f"{security_group_id}_{rule_type}_{protocol}_{from_port}_{to_port}_{source_security_group_id}"


def import_batch(
    stack_dir: str,
    specs: list[tuple[str, str]],
    region: str | None = None,
) -> int:
    """
    Run imports for (addr, resource_id) pairs. Returns count of failures.
    """
    failed = 0
    for addr, rid in specs:
        logger.info(f"Importing {addr}...")
        if not import_one_resource(stack_dir, addr, rid, region):
            failed += 1
    return failed
