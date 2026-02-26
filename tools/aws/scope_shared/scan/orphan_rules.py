"""
Orphan resource classification: resources not in Terraform state that survive teardown.

Uses pattern-based rules (no hardcoded IDs). Patterns from resource_names (PROJ_PREFIX + *_COMPONENT).
Returns: ("definitely"|"likely", note) or (None, ""). Note is for inline display.

use_elb: True = Classic ELB track (api-service-elb.yaml); False = NLB track (api-service.yaml).
Different tracks leave different orphans; notes explain context for safe cleanup.

ORPHAN_RECOVERY_HINTS: single source for recovery hints. Placeholders: <name>, <region>,
<group_id>, <oac_id>, <arn>, etc. Build hints via get_recovery_hints_for_orphans().
"""
import re
from typing import Literal

from tools.aws.scope_shared.core import resource_names

OrphanLevel = Literal["definitely", "likely"] | None
OrphanResult = tuple[OrphanLevel, str]  # (level, note)

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
# Orphan rules: pattern-based, use resource_names (prefix/env from .env)
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
    use_elb: bool = False,
) -> OrphanResult:
    """
    Classify if a resource is orphan (not in Terraform state).
    Returns (level, note): ("definitely"|"likely", note) or (None, "").
    use_elb: True = Classic ELB track; False = NLB track. Affects LB/SG/TG classification.
    """
    tags = tags or {}
    pe = f"{prefix}-{env}"
    cluster_tag_old, cluster_tag_new = resource_names.get_eks_cluster_tags(prefix, env, region)

    def _is_our_eks(t: dict) -> bool:
        return t.get(cluster_tag_old) in ("shared", "owned") or (
            cluster_tag_new and t.get(cluster_tag_new) in ("shared", "owned")
        )

    # --- CloudFront OAC ---
    if resource_type == "cloudfront_oac":
        if resource_names.get_frontend_oac_pattern(prefix, env).match(name):
            return (None, "")
        if re.match(rf"^{re.escape(prefix)}-{re.escape(env)}-frontend-oac$", name):
            return ("definitely", "legacy OAC; not in Terraform")
        return (None, "")

    # --- IAM role ---
    if resource_type == "iam_role":
        if not name.startswith(pe):
            return (None, "")
        if "-aws-load-balancer-controller" in name or "-load-balancer-controller" in name:
            return ("definitely", "AWS Load Balancer Controller; not in Terraform")
        if "-csi-driver-role" in name or "-ebs-csi-" in name:
            return ("definitely", "EKS addon; not in Terraform")
        if resource_names.is_terraform_iam_role(name, prefix, env, region):
            return (None, "")
        return ("likely", "project-named role not in Terraform list")

    # --- Security group: k8s-elb-* = in-tree Classic ELB SG ---
    if resource_type == "security_group":
        if name.startswith("k8s-elb-") and _is_our_eks(tags):
            note = "Classic ELB track: in-tree SG" if use_elb else "NLB track: Classic ELB remnant from migration"
            return ("definitely", note)
        return (None, "")

    # --- Load balancer: Classic ELB only when NLB track (when --elb, we use it) ---
    if resource_type == "load_balancer":
        if lb_type == LB_TYPE_CLASSIC:
            if use_elb:
                return (None, "")  # In use; not orphan
            return ("definitely", "NLB track: Classic ELB remnant from migration")
        return (None, "")

    # --- Target group: k8s-frukube-fruapisv-* = our API NLB; k8s-ingressn-* = NGINX ---
    if resource_type == "target_group":
        if name.startswith("k8s-frukube-fruapisv-"):
            if use_elb:
                return ("definitely", "Classic ELB track: TG from previous NLB migration")
            return (None, "")  # In use by our NLB
        if name.startswith("k8s-ingressn-"):
            return ("definitely", "NGINX Ingress; not in Terraform")
        if name.startswith("k8s-"):
            return ("definitely", "K8s-created; not in Terraform")
        return (None, "")

    return (None, "")
