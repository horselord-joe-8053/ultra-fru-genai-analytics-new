"""
Import pre-existing durable_with_cooloff resources (Secrets Manager) into Terraform state.

Resources: Secrets Manager secrets. When these exist in AWS but not in state
(e.g. after restore from scheduled deletion, or migration from durable stack),
apply fails with ResourceExistsException. Import adopts them by name.

See docs/learned/DURABLE_COOLOFF_EVALUATION.md for stack split rationale.
"""
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core import resource_names
from tools.aws.scope_shared.import_preexist._common import import_batch


def run_import_durable_cooloff(stack_dir: str, env: str, region: str | None = None) -> int:
    """
    Import pre-existing durable_with_cooloff resources (secrets) into state.
    Returns count of failures. Safe to run always; skips non-existent and already-in-state.
    """
    logger.step("Importing pre-existing durable_with_cooloff resources (secrets) into state")
    failed = 0
    deploy_region = region or "us-east-1"
    prefix = resource_names.get_proj_prefix()

    secret_specs = [
        ("aws_secretsmanager_secret.openai_api_key", f"{prefix}/{env}/openai_api_key-{deploy_region}"),
        ("aws_secretsmanager_secret.db_password", f"{prefix}/{env}/db_password-{deploy_region}"),
        ("aws_secretsmanager_secret.db_password_plain", f"{prefix}/{env}/db_password_plain-{deploy_region}"),
    ]
    failed += import_batch(stack_dir, secret_specs, region)

    if failed == 0:
        logger.success("Import phase completed (durable_with_cooloff)")
    else:
        logger.warning(f"Some imports failed ({failed}). Run 'tofu plan' to see remaining differences.")
    return failed
