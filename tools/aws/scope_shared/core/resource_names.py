"""
Centralized AWS resource name assembly (PROJ_PREFIX + *_COMPONENT convention).

Single source of truth for full resource names. Implements the naming convention
from docs/STEP_LARGE_REFACTOR_RENAMING.md Part A and C.3.

- Hyphen-style: {proj}-{component}-{env}-{region} (e.g. fru-delta-internal-dev-us-east-1)
- Path-style: /{proj}/{component}/{env}/{region} (e.g. /fru/cloud-log-group-spark/dev/us-east-1)

Backward compatibility: PROJ_PREFIX falls back to FRU_PREFIX; *_COMPONENT falls back
to legacy full-name vars when unset (during transition).
"""
import os
from typing import Literal

Style = Literal["hyphen", "path"]


def _proj_prefix() -> str:
    """Project prefix. PROJ_PREFIX preferred; fallback to FRU_PREFIX."""
    return os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")


def get_proj_prefix() -> str:
    """Public accessor for project prefix."""
    return _proj_prefix()


def _component(env_key: str, legacy_full: str | None, default: str) -> str:
    """
    Component value. Prefer *_COMPONENT; fallback to legacy full-name (parsed) or default.
    legacy_full: e.g. 'fru-dev-delta-internal' -> extract 'delta-internal' for S3_DELTA_COMPONENT.
    """
    val = os.getenv(env_key, "").strip()
    if val:
        return val
    if legacy_full:
        # Heuristic: strip leading {prefix}-{env}- to get component
        prefix = _proj_prefix()
        env = os.getenv("FRU_ENV", os.getenv("ENVIRONMENT", "dev"))
        pe = f"{prefix}-{env}-"
        if legacy_full.startswith(pe):
            return legacy_full[len(pe) :]
    return default


def _hyphen(proj: str, component: str, env: str, region: str, *, extra: str | None = None) -> str:
    """Build hyphen-style name: {proj}-{component}-{env}-{region} or with extra segment."""
    parts = [proj, component]
    if extra:
        parts.append(extra)
    parts.extend([env, region])
    return "-".join(parts)


def _path(proj: str, component: str, env: str, region: str) -> str:
    """Build path-style name: /{proj}/{component}/{env}/{region}."""
    return f"/{proj}/{component}/{env}/{region}"


# -----------------------------------------------------------------------------
# Component env keys and defaults (per STEP_LARGE_REFACTOR_RENAMING Part C.2)
# -----------------------------------------------------------------------------
_TF_STATE_BUCKET_COMPONENT = "tf-state"
_TF_LOCK_TABLE_COMPONENT = "tf-locks-tbl"
_S3_DELTA_COMPONENT = "delta-internal"
_S3_ARTIFACT_COMPONENT = "artifacts-internal"
# Regionless: same repo name in all regions. Enables push-only across regions.
_ECR_APP_COMPONENT = "api-img"
_ECR_SPARK_COMPONENT = "spark-img"
_EKS_CLUSTER_COMPONENT = "eks"
_ECS_CLUSTER_COMPONENT = "ecs"
_ALB_COMPONENT = "alb"
_LOG_GROUP_SPARK_COMPONENT = "cloud-log-group-spark"
_LOG_GROUP_ECS_API_COMPONENT = "ecs-api"


def tf_state_bucket(env: str, region: str, account_id: str) -> str:
    """TF state bucket: {proj}-{component}-{env}-{region}-{account}."""
    proj = _proj_prefix()
    comp = os.getenv("TF_STATE_BUCKET_COMPONENT", "").strip() or _TF_STATE_BUCKET_COMPONENT
    return f"{proj}-{comp}-{env}-{region}-{account_id}"


def tf_lock_table(region: str) -> str:
    """TF lock table: {proj}-{component}-{region} (no env per convention)."""
    proj = _proj_prefix()
    comp = os.getenv("TF_LOCK_TABLE_COMPONENT", "").strip() or _TF_LOCK_TABLE_COMPONENT
    return f"{proj}-{comp}-{region}"


def s3_delta_bucket(env: str, region: str) -> str:
    """S3 delta bucket: {proj}-{component}-{env}-{region}."""
    proj = _proj_prefix()
    comp = _component("S3_DELTA_COMPONENT", os.getenv("S3_DELTA_BUCKET"), _S3_DELTA_COMPONENT)
    return _hyphen(proj, comp, env, region)


def s3_artifacts_bucket(env: str, region: str) -> str:
    """S3 artifacts bucket: {proj}-{component}-{env}-{region}."""
    proj = _proj_prefix()
    comp = _component("S3_ARTIFACT_COMPONENT", os.getenv("S3_ARTIFACT_BUCKET"), _S3_ARTIFACT_COMPONENT)
    return _hyphen(proj, comp, env, region)


def ecr_repo_app(env: str, region: str = "", *, container_type: str = "") -> str:
    """ECR app repo: {proj}-{component}-{env}. Regionless so push-only works across regions."""
    proj = _proj_prefix()
    comp = _component("ECR_APP_COMPONENT", os.getenv("ECR_REPO_APP"), _ECR_APP_COMPONENT)
    if container_type:
        return f"{proj}-{container_type}-{comp}-{env}"
    return f"{proj}-{comp}-{env}"


def ecr_repo_spark(env: str, region: str = "", *, container_type: str = "") -> str:
    """ECR spark repo: {proj}-{component}-{env}. Regionless so push-only works across regions."""
    proj = _proj_prefix()
    comp = _component("ECR_SPARK_COMPONENT", os.getenv("ECR_REPO_SPARK"), _ECR_SPARK_COMPONENT)
    if container_type:
        return f"{proj}-{container_type}-{comp}-{env}"
    return f"{proj}-{comp}-{env}"


def eks_cluster(env: str, region: str) -> str:
    """EKS cluster: {proj}-{component}-{env}-{region}."""
    proj = _proj_prefix()
    comp = _component("EKS_CLUSTER_COMPONENT", os.getenv("EKS_CLUSTER_NAME"), _EKS_CLUSTER_COMPONENT)
    return _hyphen(proj, comp, env, region)


def ecs_cluster(env: str, region: str) -> str:
    """ECS cluster: {proj}-{component}-{env}-{region}."""
    proj = _proj_prefix()
    comp = _component("ECS_CLUSTER_COMPONENT", os.getenv("ECS_CLUSTER_NAME"), _ECS_CLUSTER_COMPONENT)
    return _hyphen(proj, comp, env, region)


def alb_name(env: str, region: str) -> str:
    """ALB name: {proj}-{component}-{env}-{region}."""
    proj = _proj_prefix()
    comp = os.getenv("ALB_COMPONENT", "").strip() or _ALB_COMPONENT
    return _hyphen(proj, comp, env, region)


def log_group_spark(env: str, region: str) -> str:
    """Log group (spark): /{proj}/{component}/{env}/{region}."""
    proj = _proj_prefix()
    comp = (
        os.getenv("CLOUDWATCH_LOG_GROUP_SPARK", "").strip()
        or _LOG_GROUP_SPARK_COMPONENT
    )
    return _path(proj, comp, env, region)


def log_group_ecs_api(env: str, region: str) -> str:
    """Log group (ecs-api): /{proj}/{component}/{env}/{region}."""
    proj = _proj_prefix()
    comp = (
        os.getenv("CLOUDWATCH_LOG_GROUP_ECS_API", "").strip()
        or _LOG_GROUP_ECS_API_COMPONENT
    )
    return _path(proj, comp, env, region)


def rds_log_group(env: str) -> str:
    """RDS Aurora log group: /aws/rds/cluster/{proj}-{env}-aurora-cluster/postgresql."""
    proj = _proj_prefix()
    return f"/aws/rds/cluster/{proj}-{env}-aurora-cluster/postgresql"


def ecs_container_insights_log_group(env: str) -> str:
    """ECS Container Insights log group: /aws/ecs/containerinsights/{proj}-{env}-cluster/performance."""
    proj = _proj_prefix()
    return f"/aws/ecs/containerinsights/{proj}-{env}-cluster/performance"


def ecr_image_uri(component: str, env: str, region: str, tag: str = "latest") -> str:
    """Full ECR image URI: {account}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}."""
    from tools.aws.scope_shared.core.backend import get_account_id
    account = get_account_id()
    if component == "app":
        repo = ecr_repo_app(env, region)
    else:
        repo = ecr_repo_spark(env, region)
    return f"{account}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"


# -----------------------------------------------------------------------------
# Scan / orphan: project resource matching (no hardcoding; uses .env convention)
# -----------------------------------------------------------------------------


def _get_s3_delta_component() -> str:
    """S3 delta component from .env."""
    return _component("S3_DELTA_COMPONENT", os.getenv("S3_DELTA_BUCKET"), _S3_DELTA_COMPONENT)


def _get_s3_artifact_component() -> str:
    """S3 artifacts component from .env."""
    return _component("S3_ARTIFACT_COMPONENT", os.getenv("S3_ARTIFACT_BUCKET"), _S3_ARTIFACT_COMPONENT)


def _get_ecr_app_component() -> str:
    """ECR app component from .env."""
    return _component("ECR_APP_COMPONENT", os.getenv("ECR_REPO_APP"), _ECR_APP_COMPONENT)


def _get_ecr_spark_component() -> str:
    """ECR spark component from .env."""
    return _component("ECR_SPARK_COMPONENT", os.getenv("ECR_REPO_SPARK"), _ECR_SPARK_COMPONENT)


def _get_log_group_spark_component() -> str:
    """Log group spark component from .env."""
    return os.getenv("CLOUDWATCH_LOG_GROUP_SPARK", "").strip() or _LOG_GROUP_SPARK_COMPONENT


def _get_log_group_ecs_api_component() -> str:
    """Log group ecs-api component from .env."""
    return os.getenv("CLOUDWATCH_LOG_GROUP_ECS_API", "").strip() or _LOG_GROUP_ECS_API_COMPONENT


def is_project_resource_name(
    name: str, resource_type: str, env: str, region: str = "", prefix: str | None = None
) -> bool:
    """
    Return True if name matches our project's resource naming (from .env convention).
    Used by scan and orphan logic. No hardcoded component names.
    prefix: override from caller (e.g. scan --prefix); if None, use PROJ_PREFIX from .env.
    """
    proj = prefix if prefix is not None else _proj_prefix()
    pe = f"{proj}-{env}"
    pe_slash = f"{proj}/{env}"

    if resource_type == "s3":
        delta = s3_delta_bucket(env, region)
        artifacts = s3_artifacts_bucket(env, region)
        delta_comp = _get_s3_delta_component()
        artifact_comp = _get_s3_artifact_component()
        tf_state_comp = os.getenv("TF_STATE_BUCKET_COMPONENT", "").strip() or _TF_STATE_BUCKET_COMPONENT
        return (
            name == delta
            or name == artifacts
            or name.startswith(pe)
            or f"-{pe}-" in name
            or name.startswith(f"{proj}-{tf_state_comp}")
            or name.startswith(f"{proj}-tf-")
            or (name.startswith(proj) and env in name and (f"-{delta_comp}-" in name or f"-{artifact_comp}-" in name or "-frontend-" in name or "terraform-state" in name or "tf-state" in name))
        )

    if resource_type == "ecr":
        app_repo = ecr_repo_app(env, region)
        spark_repo = ecr_repo_spark(env, region)
        return name == app_repo or name == spark_repo or pe in name or name.startswith(pe) or (name.startswith(proj) and env in name)

    if resource_type == "ecs_cluster":
        expected = ecs_cluster(env, region)
        return name == expected or name.startswith(pe) or (name.startswith(proj) and env in name)

    if resource_type == "eks_cluster":
        expected = eks_cluster(env, region)
        return name == expected or name.startswith(pe) or (name.startswith(proj) and env in name)

    if resource_type == "alb" or resource_type == "target_group":
        expected_alb = alb_name(env, region)
        eks_name = eks_cluster(env, region)
        eks_no_hyphen = eks_name.replace("-", "")
        return (
            name == expected_alb
            or name.startswith(f"{expected_alb}-")
            or name.startswith(pe)
            or f"{pe}-" in name
            or (name.startswith(proj) and env in name)
            or name.startswith("k8s-frukube-fruapisv-")  # k8s NLB/TG for fru-api-svc in fru-kube ns
            or name.startswith(f"k8s-traffic-{eks_no_hyphen}")  # k8s traffic SG for our EKS
        )

    if resource_type == "security_group":
        eks_name = eks_cluster(env, region)
        eks_no_hyphen = eks_name.replace("-", "")
        return (
            name.startswith(proj)
            or name.startswith("k8s-frukube-fruapisv-")  # k8s SG for fru-api-svc in fru-kube ns
            or name.startswith(f"k8s-traffic-{eks_no_hyphen}")  # k8s traffic SG for our EKS
        )

    if resource_type == "log_group":
        lg_spark = log_group_spark(env, region)
        lg_ecs = log_group_ecs_api(env, region)
        rds_lg = rds_log_group(env)
        ecs_ci = ecs_container_insights_log_group(env)
        eks_cluster_name = eks_cluster(env, region)
        spark_comp = _get_log_group_spark_component()
        ecs_comp = _get_log_group_ecs_api_component()
        return (
            name == lg_spark
            or name == lg_ecs
            or name.startswith(rds_lg)
            or name.startswith(ecs_ci)
            or f"/aws/eks/{eks_cluster_name}" in name
            or f"/{proj}/{env}" in name
            or (f"/{proj}/" in name and (spark_comp in name or ecs_comp in name))
        )

    if resource_type == "secret":
        return name.startswith(pe_slash)

    if resource_type == "ebs_volume":
        return f"{eks_cluster(env, region)}" in name or pe in name or f"{pe}-eks" in name

    if resource_type == "eventbridge_rule":
        return name == f"{pe}-spark-schedule" or name.startswith(pe)

    if resource_type == "vpc":
        return name.startswith(pe)

    if resource_type == "rds_cluster":
        return name.startswith(f"{pe}-aurora-cluster") or name.startswith(pe)

    if resource_type == "iam_role":
        eks_comp = _component("EKS_CLUSTER_COMPONENT", os.getenv("EKS_CLUSTER_NAME"), _EKS_CLUSTER_COMPONENT)
        eks_prefix = f"{proj}-{eks_comp}-{env}"
        return (
            name.startswith(pe)
            or name.startswith(f"{proj}-eks-")  # EKS cluster/node roles: fru-eks-dev-us-east-2-*
            or name.startswith(eks_prefix)
            or (name.startswith("eksctl-") and f"{proj}-{eks_comp}-{env}" in name)  # eksctl-fru-eks-dev-us-east-*-addon-*
            or name == "eks-ebs-csi-driver-role"  # EKS addon role (standard name, created by our EKS)
        )

    if resource_type == "cloudfront_dist" or resource_type == "cloudfront_oac":
        return f"{proj}-{env}-frontend" in name

    return False


def classify_project_category_from_name(
    name: str, resource_type: str, env: str, region: str = "", prefix: str | None = None
) -> str:
    """
    Classify a project resource into FRU_CATEGORIES (kube, nonkube, shared-*, other).
    Uses resource_names for component-aware matching. No hardcoded component strings.
    prefix: override from caller; if None, use PROJ_PREFIX from .env.
    """
    proj = prefix if prefix is not None else _proj_prefix()
    pe = f"{proj}-{env}"
    eks_name = eks_cluster(env, region)
    delta_comp = _get_s3_delta_component()
    artifact_comp = _get_s3_artifact_component()
    app_comp = _get_ecr_app_component()
    spark_comp = _get_ecr_spark_component()
    lg_spark_comp = _get_log_group_spark_component()
    lg_ecs_comp = _get_log_group_ecs_api_component()

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
        if name.startswith("k8s-frukube-fruapisv-") or name.startswith(f"k8s-traffic-{eks_name.replace('-', '')}"):
            return "kube"
        if "aurora" in name:
            return "shared-durable"
        return "other"
    if resource_type == "log_group":
        if f"/aws/eks/{eks_name}" in name:
            return "kube"
        if f"/aws/rds/cluster/{pe}-aurora-cluster" in name:
            return "shared-durable"
        if f"/aws/ecs/containerinsights/{pe}-" in name:
            return "kube"
        if f"/{proj}/{env}" in name:
            return "nonkube"
        if f"/{proj}/" in name and (lg_spark_comp in name or lg_ecs_comp in name):
            return "nonkube"
        return "other"
    if resource_type == "eventbridge_rule":
        return "nonkube"
    if resource_type == "vpc":
        return "shared-durable"
    if resource_type == "rds_cluster":
        return "shared-durable"
    if resource_type == "secret":
        # Secrets Manager secrets from durable_with_cooloff stack
        return "shared-durable-with-cooloff"
    if resource_type == "ecr":
        if f"-{app_comp}-" in name or f"-{spark_comp}-" in name:
            return "shared-nondurable"
        return "other"
    if resource_type == "ebs_volume":
        return "kube"
    if resource_type == "cloudfront_dist" or resource_type == "cloudfront_oac":
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
        if f"-{delta_comp}" in name and region in name:
            return "shared-nondurable"
        if f"-{artifact_comp}" in name and region in name:
            return "shared-nondurable"
        if "terraform-state" in name or "tf-state" in name:
            return "shared-durable"
        return "other"

    return "other"


def is_terraform_iam_role(name: str, prefix: str, env: str, region: str = "") -> bool:
    """
    Return True if name is a Terraform-created IAM role (ECS or EKS).
    Used by orphan_rules to exclude from orphan classification.
    """
    pe = f"{prefix}-{env}"
    eks_comp = _component("EKS_CLUSTER_COMPONENT", os.getenv("EKS_CLUSTER_NAME"), _EKS_CLUSTER_COMPONENT)
    eks_prefix = f"{prefix}-{eks_comp}-{env}-"

    # ECS roles (prefix-env-*-region)
    ecs_patterns = [
        f"{pe}-ecs-exec",
        f"{pe}-ecs-task",
        f"{pe}-spark-task-exec",
        f"{pe}-spark-task",
        f"{pe}-events-invoke-ecs",
    ]
    for pat in ecs_patterns:
        if pat in name or name.startswith(pat):
            return True

    # EKS roles: old format prefix-env-eks-* or new format prefix-eks-env-region-*
    if f"{pe}-eks-cluster-role" in name or f"{pe}-eks-node-role" in name:
        return True
    if name.startswith(eks_prefix) and ("-cluster-role-" in name or "-node-role-" in name):
        return True

    return False


def get_eks_cluster_tags(prefix: str, env: str, region: str = "") -> tuple[str, str]:
    """
    Return (cluster_tag_old, cluster_tag_new) for EKS cluster ownership checks.
    Old: kubernetes.io/cluster/prefix-env-eks; New: kubernetes.io/cluster/prefix-eks-env-region.
    """
    pe = f"{prefix}-{env}"
    eks_comp = _component("EKS_CLUSTER_COMPONENT", os.getenv("EKS_CLUSTER_NAME"), _EKS_CLUSTER_COMPONENT)
    tag_old = f"kubernetes.io/cluster/{pe}-eks"
    tag_new = f"kubernetes.io/cluster/{prefix}-{eks_comp}-{env}-{region}" if region else ""
    return tag_old, tag_new


def get_frontend_oac_pattern(prefix: str, env: str):
    """Return compiled regex for Terraform-created OAC names. Used by orphan_rules."""
    import re
    pe = f"{prefix}-{env}"
    return re.compile(rf"^{re.escape(prefix)}-{re.escape(env)}-frontend-(?:kube|nonkube)-[a-z0-9-]+-oac$")
