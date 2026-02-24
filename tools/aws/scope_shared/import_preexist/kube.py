"""
Import pre-existing kube stack resources into Terraform state.

Resources: EKS IAM roles (cluster, nodes), S3 frontend bucket, CloudFront OAC.
When these exist in AWS but not in state (e.g. after brutal removal or partial teardown),
apply fails with EntityAlreadyExists.
"""
import json
import subprocess

from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.import_preexist._common import import_batch, import_one_resource


def _aws_json(cmd: list[str], region: str | None) -> dict:
    """Run AWS CLI, return parsed JSON. Returns {} on failure."""
    full = ["aws"] + cmd
    if region:
        full += ["--region", region]
    try:
        out = subprocess.run(full, capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout:
            return json.loads(out.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return {}


def _get_account_id() -> str:
    """Get current AWS account ID."""
    data = _aws_json(["sts", "get-caller-identity"], None)
    return data.get("Account", "")


def _get_oac_id(name: str) -> str:
    """Get CloudFront OAC ID by name. CloudFront API is global, endpoint is us-east-1 only."""
    marker = ""
    while True:
        cmd = ["cloudfront", "list-origin-access-controls", "--max-items", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd, "us-east-1")
        oac_list = data.get("OriginAccessControlList", {})
        for item in oac_list.get("Items") or []:
            if item.get("Name") == name:
                return item.get("Id", "")
        marker = oac_list.get("NextMarker", "")
        if not marker:
            break
    return ""


def run_import_kube(
    stack_dir: str,
    env: str,
    region: str | None = None,
    prefix: str = "fru",
    eks_cluster_name: str | None = None,
) -> int:
    """
    Import pre-existing kube resources. Returns count of failures.
    Safe to run always; skips non-existent and already-in-state.
    """
    logger.step("Importing pre-existing kube resources into state")

    cluster_name = eks_cluster_name or f"{prefix}-{env}-eks"
    deploy_region = region or "us-east-1"

    # EKS IAM roles (ID = role name)
    # Region suffix: per-region names avoid cross-region teardown deleting shared roles
    role_specs = [
        ("module.eks.aws_iam_role.eks_cluster", f"{cluster_name}-cluster-role-{deploy_region}"),
        ("module.eks.aws_iam_role.eks_nodes", f"{cluster_name}-node-role-{deploy_region}"),
    ]
    failed = import_batch(stack_dir, role_specs, region)

    # S3 bucket: prefix-env-frontend-kube-{region}-{account_id} (matches Terraform, derived from --cloud-region)
    deploy_region = region or "us-east-1"
    account_id = _get_account_id()
    bucket_name = f"{prefix}-{env}-frontend-kube-{deploy_region}-{account_id}" if account_id else ""
    if account_id:
        if not import_one_resource(
            stack_dir,
            "module.frontend.aws_s3_bucket.frontend",
            bucket_name,
            region,
        ):
            failed += 1
    else:
        logger.warning("  Skip S3 bucket: could not get account ID")

    # CloudFront OAC: import by OAC ID (look up by name). OAC is region-scoped (name includes region).
    oac_name = f"{prefix}-{env}-frontend-kube-{deploy_region}-oac"
    oac_id = _get_oac_id(oac_name)
    if oac_id:
        logger.info("  CloudFront OAC (region-scoped); adopting into state if it exists")
        if not import_one_resource(
            stack_dir,
            "module.frontend.aws_cloudfront_origin_access_control.frontend",
            oac_id,
            region,
        ):
            failed += 1
    else:
        logger.info(f"  Skip OAC (not found in AWS): {oac_name}")

    if failed == 0:
        logger.success("Import phase completed (kube)")
    else:
        logger.warning(f"Some imports failed ({failed}). Run 'tofu plan' to see remaining differences.")
    return failed
