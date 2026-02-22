"""
Orphan resource classification: resources not in Terraform state that survive teardown.

Uses pattern-based rules (no hardcoded IDs). All patterns use dynamic prefix/env.
Returns: "definitely" | "likely" | None (not orphan).

ORPHAN_RECOVERY_HINTS: single source for recovery hints. Placeholders: <name>, <region>,
<group_id>, <oac_id>, <arn>, etc. Build hints via get_recovery_hints_for_orphans().
"""
import re
from typing import Literal

OrphanLevel = Literal["definitely", "likely"] | None

# ELB type: Classic ELB (elb API) vs ALB/NLB (elbv2). We only classify Classic as orphan.
LB_TYPE_CLASSIC = "classic"

# -----------------------------------------------------------------------------
# Recovery hints: resource_type -> template (placeholders: <name>, <region>, etc.)
# Single source of truth. Add new types here when extending orphan classification.
# -----------------------------------------------------------------------------
ORPHAN_RECOVERY_HINTS: dict[str, str] = {
    "cloudfront_oac": "aws cloudfront get-origin-access-control --id <oac_id> (before delete) to capture config",
    "iam_role": "aws iam get-role --role-name <name>; aws iam list-attached-role-policies --role-name <name>",
    "load_balancer": "Classic ELB: aws elb describe-load-balancers --load-balancer-names <name> --region <region>",
    "security_group": "aws ec2 describe-security-groups --group-ids <group_id> --region <region>",
    "target_group": "aws elbv2 describe-target-groups --target-group-arns <arn> --region <region>",
    # Future orphan types (extend when adding to classify_orphan):
    "ecr_repository": "aws ecr describe-repositories --repository-names <name> --region <region>",
    "s3_bucket": "aws s3api get-bucket-location --bucket <name>; aws s3api get-bucket-tagging --bucket <name>",
    "log_group": "aws logs describe-log-groups --log-group-name-prefix <name> --region <region>",
    "ebs_volume": "aws ec2 describe-volumes --volume-ids <volume_id> --region <region>",
    "secret": "aws secretsmanager describe-secret --secret-id <name> --region <region>",
    "vpc": "aws ec2 describe-vpcs --vpc-ids <vpc_id> --region <region>",
    "rds_cluster": "aws rds describe-db-clusters --db-cluster-identifier <name> --region <region>",
    "eventbridge_rule": "aws events describe-rule --name <name> --region <region>",
    "cloudfront_dist": "aws cloudfront get-distribution --id <dist_id>",
}

GENERIC_RECOVERY_HINT = "Capture full resource state via AWS CLI/Console before delete. Check record for identifiers."


def get_recovery_hints_for_orphans(orphans: list[dict]) -> dict[str, str]:
    """Build recovery hints for resource types present in orphans. Uses registry + generic fallback."""
    types_seen = {r.get("resource_type", "") for r in orphans if r.get("resource_type")}
    return {
        rt: ORPHAN_RECOVERY_HINTS.get(rt, GENERIC_RECOVERY_HINT)
        for rt in types_seen
    }


# -----------------------------------------------------------------------------
# Terraform-created resource patterns (we know these are in state)
# Used to exclude from orphan classification.
# -----------------------------------------------------------------------------
def _terraform_iam_role_patterns(prefix: str, env: str) -> list[str]:
    """IAM roles created by our Terraform. Pattern substrings."""
    pe = f"{prefix}-{env}"
    return [
        f"{pe}-ecs-exec",
        f"{pe}-ecs-task",
        f"{pe}-spark-task-exec",
        f"{pe}-spark-task",
        f"{pe}-events-invoke-ecs",
        f"{pe}-eks-cluster-role",
        f"{pe}-eks-node-role",
    ]


def _terraform_oac_pattern(prefix: str, env: str) -> re.Pattern:
    """OAC names we create: {prefix}-{env}-frontend-{suffix}-{region}-oac."""
    return re.compile(rf"^{re.escape(prefix)}-{re.escape(env)}-frontend-(?:kube|nonkube)-[a-z0-9-]+-oac$")


# -----------------------------------------------------------------------------
# Orphan rules: pattern-based, use prefix/env (no hardcoded values)
# -----------------------------------------------------------------------------


def classify_orphan(
    resource_type: str,
    name: str,
    prefix: str,
    env: str,
    *,
    tags: dict[str, str] | None = None,
    lb_type: str = "",
    region: str = "",
) -> OrphanLevel:
    """
    Classify if a resource is orphan (not in Terraform state).
    Returns "definitely", "likely", or None.
    """
    tags = tags or {}
    pe = f"{prefix}-{env}"
    cluster_tag = f"kubernetes.io/cluster/{pe}-eks"

    # --- CloudFront OAC ---
    if resource_type == "cloudfront_oac":
        # Our Terraform: *-frontend-{suffix}-{region}-oac. Legacy: *-frontend-oac (no suffix/region).
        if _terraform_oac_pattern(prefix, env).match(name):
            return None
        if re.match(rf"^{re.escape(prefix)}-{re.escape(env)}-frontend-oac$", name):
            return "definitely"
        return None

    # --- IAM role ---
    if resource_type == "iam_role":
        if not name.startswith(pe):
            return None
        # External controller roles (never in our Terraform)
        if "-aws-load-balancer-controller" in name or "-load-balancer-controller" in name:
            return "definitely"
        if "-csi-driver-role" in name or "-ebs-csi-" in name:
            return "definitely"
        # Check against Terraform-created roles
        for pat in _terraform_iam_role_patterns(prefix, env):
            if pat in name or name == pat:
                return None
        # Project-named role not in our Terraform list
        return "likely"

    # --- Security group: k8s-elb-* with our cluster tag = created by K8s, not Terraform ---
    if resource_type == "security_group":
        if name.startswith("k8s-elb-") and tags.get(cluster_tag) in ("shared", "owned"):
            return "definitely"
        return None

    # --- Load balancer ---
    if resource_type == "load_balancer":
        # Classic ELB: we never use Classic in Terraform (we use ALB/NLB).
        if lb_type == LB_TYPE_CLASSIC:
            return "definitely"
        return None

    # --- Target group: k8s-ingressn-* = created by K8s Ingress, not Terraform ---
    if resource_type == "target_group":
        if name.startswith("k8s-"):
            return "definitely"
        return None

    return None
