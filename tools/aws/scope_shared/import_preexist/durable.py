"""
Import pre-existing durable stack resources into Terraform state.

Resources: Secrets Manager secrets. When these exist in AWS but not in state
(e.g. after restore from scheduled deletion), apply fails with ResourceExistsException.
"""
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core import resource_names
from tools.aws.scope_shared.import_preexist._common import import_batch


def run_import_durable(stack_dir: str, env: str, region: str | None = None) -> int:
    """
    Import pre-existing durable resources (secrets). Returns count of failures.
    Safe to run always; skips non-existent and already-in-state.
    """
    logger.step("Importing pre-existing durable resources (secrets) into state")
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
        logger.success("Import phase completed (durable)")
    else:
        logger.warning(f"Some imports failed ({failed}). Run 'tofu plan' to see remaining differences.")
    return failed
