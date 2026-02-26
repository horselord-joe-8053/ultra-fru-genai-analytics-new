"""
Centralized AWS scan configuration: categories, patterns, classification.

Used by resources_scan/scan_aws_remaining.py to:
- Define FRU project resource categories (kube, nonkube, shared-nondurable, shared-durable, other)
- Identify project resources (dynamic from .env via resource_names)
- Identify AWS built-in vs other projects (cost concern)

Search criteria: PROJ_PREFIX + *_COMPONENT from .env per docs/STEP_LARGE_REFACTOR_RENAMING.md.
"""
import re

from tools.aws.scope_shared.core import resource_names

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
    Return True if the resource belongs to this project.
    Uses resource_names (PROJ_PREFIX + *_COMPONENT from .env). No hardcoding.
    prefix param is passed through for scan CLI override; resource_names uses .env internally.
    """
    return resource_names.is_project_resource_name(name, resource_type, env, region, prefix=prefix)


def classify_project_category(
    name: str,
    resource_type: str,
    prefix: str,
    env: str,
    region: str = "",
) -> str:
    """
    Classify a project resource into FRU_CATEGORIES.
    Uses resource_names (component-aware from .env). No hardcoding.
    """
    return resource_names.classify_project_category_from_name(name, resource_type, env, region, prefix=prefix)
