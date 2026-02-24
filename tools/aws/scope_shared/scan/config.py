"""
Centralized AWS scan configuration: categories, patterns, classification.

Used by resources_scan/scan_aws_remaining.py to:
- Define FRU project resource categories (kube, nonkube, shared-nondurable, shared-durable, other)
- Identify project resources (dynamic prefix/env)
- Identify AWS built-in vs other projects (cost concern)
"""
import re

# -----------------------------------------------------------------------------
# FRU project categories (scope-based)
# -----------------------------------------------------------------------------
FRU_CATEGORIES = [
    "kube",
    "nonkube",
    "shared-nondurable",
    "shared-durable",
    "other",
]

# Resource type -> category mapping for project resources (when name patterns don't suffice)
_RESOURCE_TYPE_TO_CATEGORY: dict[str, str] = {
    "ecs_cluster": "nonkube",
    "eks_cluster": "kube",
    "alb": "nonkube",
    "target_group": "nonkube",
    "log_group_nonkube": "nonkube",
    "log_group_kube": "kube",
    "eventbridge_rule": "nonkube",
    "vpc": "shared-durable",
    "rds_cluster": "shared-durable",
    "secret": "shared-durable",
    "ecr": "shared-nondurable",
    "cloudfront_dist": "other",  # overridden by comment
    "cloudfront_oac": "other",  # overridden by name
}


# -----------------------------------------------------------------------------
# AWS built-in patterns (no cost to you; AWS-managed)
# -----------------------------------------------------------------------------
AWS_BUILTIN_PATTERNS = [
    r"^default$",  # default VPC
    r"^aws-",  # aws-elasticache-*, aws-rds-*, etc.
    r"^AWS",  # AWSReserved*, etc.
    r"^amazon-",
    r"^Amazon",
    r"^AWSServiceRole",
    r"^aws-service-role",
    r"^eksctl-.*-cluster-ServiceRole",
    r"^eksctl-.*-nodegroup-.*-NodeInstanceRole",
    r"^EC2ContainerService",
    r"^elasticbeanstalk-",
    r"^CloudWatch",
    r"^AWSLambda",
    r"^service-role/",
    r"^system/",
    r"^\.terraform",
    r"^terraform-",
    r"^cdk-",
    r"^stack-",
    r"^Default",
    r"^default-",
]
_AWS_BUILTIN_RE = re.compile("|".join(f"({p})" for p in AWS_BUILTIN_PATTERNS))


def is_aws_builtin(identifier: str, resource_type: str = "") -> bool:
    """
    Return True if the resource appears to be AWS-managed (built-in).
    These typically don't incur direct cost or are required by AWS services.
    """
    name = identifier.split(":")[-1] if ":" in identifier else identifier
    # Strip parenthetical suffixes for matching
    name = re.sub(r"\s*\([^)]*\)\s*\[.*\]$", "", name).strip()
    return bool(_AWS_BUILTIN_RE.search(name))


def is_project_resource(
    name: str,
    resource_type: str,
    prefix: str,
    env: str,
    region: str = "",
) -> bool:
    """
    Return True if the resource belongs to this project (prefix/env).
    Uses dynamic prefix and env from args.
    """
    pe = f"{prefix}-{env}"
    pe_slash = f"{prefix}/{env}"

    if resource_type == "s3":
        return (
            name.startswith(pe)
            or f"-{pe}-" in name
            or name.startswith(f"{prefix}-terraform-state")
            or name.startswith(f"{prefix}-tf-state")
        )
    if resource_type == "ecr":
        return pe in name or name.startswith(pe)
    if resource_type == "ecs_cluster":
        return name.startswith(pe)
    if resource_type == "eks_cluster":
        return name.startswith(pe)
    if resource_type == "alb" or resource_type == "target_group":
        return name.startswith(pe) or f"{pe}-" in name
    if resource_type == "security_group":
        return name.startswith(prefix)  # fru-dev-*, fru-ecs-*
    if resource_type == "log_group":
        return (
            f"/{prefix}/{env}" in name
            or f"/aws/eks/{pe}-eks" in name
            or f"/aws/rds/cluster/{pe}-aurora-cluster" in name
            or f"/aws/ecs/containerinsights/{pe}-" in name
        )
    if resource_type == "secret":
        return name.startswith(pe_slash)
    if resource_type == "ebs_volume":
        return f"{pe}-eks" in name or pe in name
    if resource_type == "eventbridge_rule":
        return name.startswith(pe)
    if resource_type == "vpc":
        return name.startswith(pe)
    if resource_type == "rds_cluster":
        return name.startswith(pe)
    if resource_type == "iam_role":
        return name.startswith(pe)
    if resource_type == "cloudfront_dist":
        return f"{prefix}-{env}-frontend" in name
    if resource_type == "cloudfront_oac":
        return f"{prefix}-{env}-frontend" in name
    return False


def classify_project_category(
    name: str,
    resource_type: str,
    prefix: str,
    env: str,
    region: str = "",
) -> str:
    """
    Classify a project resource into FRU_CATEGORIES.
    Returns category string.
    """
    if resource_type == "ecs_cluster":
        return "nonkube"
    if resource_type == "eks_cluster":
        return "kube"
    if resource_type == "alb" or resource_type == "target_group":
        return "nonkube"
    if resource_type == "security_group":
        if "alb" in name or "ecs-tasks" in name:
            return "nonkube"
        if "eks" in name or "eksctl" in name:
            return "kube"
        if "aurora" in name:
            return "shared-durable"
        return "other"
    if resource_type == "log_group":
        if f"/aws/eks/{prefix}-{env}-eks" in name:
            return "kube"
        if f"/aws/rds/cluster/{prefix}-{env}-aurora-cluster" in name:
            return "shared-durable"
        if f"/aws/ecs/containerinsights/{prefix}-{env}-" in name:
            return "kube"
        if f"/{prefix}/{env}" in name:
            return "nonkube"
        return "other"
    if resource_type == "eventbridge_rule":
        return "nonkube"
    if resource_type == "vpc":
        return "shared-durable"
    if resource_type == "rds_cluster":
        return "shared-durable"
    if resource_type == "secret":
        return "shared-durable"
    if resource_type == "ecr":
        if "-api-" in name or "-spark-" in name:
            return "shared-nondurable"
        return "other"
    if resource_type == "ebs_volume":
        return "kube"
    if resource_type == "cloudfront_dist":
        if "kube" in name:
            return "kube"
        if "nonkube" in name:
            return "nonkube"
        return "other"
    if resource_type == "cloudfront_oac":
        if "kube" in name:
            return "kube"
        if "nonkube" in name:
            return "nonkube"
        return "other"
    if resource_type == "iam_role":
        if "ecs" in name or "events-invoke" in name or "spark" in name:
            return "nonkube"
        if "eks" in name:
            return "kube"
        return "other"
    if resource_type == "s3":
        if "-frontend-kube-" in name and region in name:
            return "kube"
        if "-frontend-nonkube-" in name and region in name:
            return "nonkube"
        if "-delta" in name and region in name:
            return "shared-nondurable"
        if "-artifacts" in name and region in name:
            return "shared-nondurable"
        if "terraform-state" in name or "tf-state" in name:
            return "shared-durable"
        return "other"

    return _RESOURCE_TYPE_TO_CATEGORY.get(resource_type, "other")
