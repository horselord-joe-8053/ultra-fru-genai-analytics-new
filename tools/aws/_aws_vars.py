
import os
from tools._env import require

# Map .env keys to Terraform variable names
MAP = {
    "FRU_ENV": "env",
    "FRU_PREFIX": "prefix",
    "CLOUD_REGION": "aws_region",
    "TF_STATE_BUCKET": "tf_state_bucket",
    "TF_LOCK_TABLE": "tf_lock_table",
    "VPC_CIDR": "vpc_cidr",
    "S3_DELTA_BUCKET": "delta_bucket",
    "S3_ARTIFACT_BUCKET": "artifacts_bucket",
    "ECR_REPO_APP": "ecr_repo_app",
    "ECR_REPO_SPARK": "ecr_repo_spark",
    "ECS_CLUSTER_NAME": "ecs_cluster_name",
    "EKS_CLUSTER_NAME": "eks_cluster_name",
    "ALB_NAME": "alb_name",
    "APP_IMAGE_TAG": "app_image_tag",
    "SPARK_IMAGE_TAG": "spark_image_tag",
    "LOG_LEVEL": "log_level",
    "ALLOWED_ORIGINS": "allowed_origins",
    "USE_AGENT_QUERY": "use_agent_query",
    "OPENAI_EMBED_MODEL": "openai_embed_model",
    "ENABLE_ANALYTICS_SCHEDULER": "enable_analytics_scheduler",
    "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": "analytics_scheduler_interval_seconds",
    "DELTA_TABLE_PATH": "delta_table_path",
    "DELTA_LAKE_PACKAGE": "delta_lake_package",
    "AWS_BEDROCK_INFERENCE_PROFILE_ID": "bedrock_inference_profile_id",
    "AWS_BEDROCK_MODEL_ID": "bedrock_model_id",
}

def get_base_vars(env: str, region: str | None = None):
    """
    Set TF_VAR_ environment variables for OpenTofu.
    Returns an empty list to maintain compatibility with existing script signatures.
    If region is provided, uses it for aws_region TF var and sets CLOUD_REGION/AWS_REGION in env for subprocesses.
    """
    prefix = os.getenv("FRU_PREFIX", "fru")

    if region:
        os.environ["CLOUD_REGION"] = region
        os.environ["AWS_REGION"] = region
        os.environ["AWS_DEFAULT_REGION"] = region

    # helper to set TF_VAR
    def set_tf(name, val):
        os.environ[f"TF_VAR_{name}"] = str(val)

    set_tf("env", env)
    set_tf("prefix", prefix)

    # TF State Prefix logic
    tf_state_prefix = os.getenv("TF_STATE_PREFIX") or prefix
    set_tf("tf_state_prefix", tf_state_prefix)

    # Map everything else from env
    for env_key, tf_key in MAP.items():
        val = os.getenv(env_key)
        if val:
            set_tf(tf_key, val)

    # CRITICAL: Ensure aws_region is explicitly set (use region param or CLOUD_REGION)
    if not os.getenv("TF_VAR_aws_region"):
        set_tf("aws_region", region or os.getenv("CLOUD_REGION", "").strip() or require("AWS_REGION"))

    # DEFAULTS for names if missing
    if not os.getenv("TF_VAR_ecs_cluster_name"):
        set_tf("ecs_cluster_name", f"{prefix}-{env}-ecs")
    if not os.getenv("TF_VAR_eks_cluster_name"):
        default_eks = f"{prefix}-{env}-eks"
        set_tf("eks_cluster_name", default_eks)
        if not os.getenv("EKS_CLUSTER_NAME"):
            os.environ["EKS_CLUSTER_NAME"] = default_eks  # eks_kubeconfig needs this
    if not os.getenv("TF_VAR_alb_name"):
        set_tf("alb_name", f"{prefix}-{env}-alb")
    if not os.getenv("TF_VAR_delta_bucket"):
        set_tf("delta_bucket", f"{prefix}-{env}-delta")
    if not os.getenv("TF_VAR_artifacts_bucket"):
        set_tf("artifacts_bucket", f"{prefix}-{env}-artifacts")
    if not os.getenv("TF_VAR_tf_lock_table"):
        set_tf("tf_lock_table", f"{prefix}-{env}-lock")
    # ECR repo names include container type (kube or nonkube)
    container_type = os.getenv("CONTAINER_TYPE", "")
    if not os.getenv("TF_VAR_ecr_repo_app"):
        ecr_app_name = f"{prefix}-{container_type}-{env}-api" if container_type else f"{prefix}-{env}-api"
        set_tf("ecr_repo_app", ecr_app_name)
    if not os.getenv("TF_VAR_ecr_repo_spark"):
        ecr_spark_name = f"{prefix}-{container_type}-{env}-spark" if container_type else f"{prefix}-{env}-spark"
        set_tf("ecr_repo_spark", ecr_spark_name)

    # Construct full images if component vars are present
    repo_app = os.getenv("ECR_REPO_APP") or os.getenv("TF_VAR_ecr_repo_app")
    tag_app = os.getenv("APP_IMAGE_TAG", "latest")
    if repo_app and not os.getenv("TF_VAR_app_image"):
        set_tf("app_image", f"{repo_app}:{tag_app}")

    repo_spark = os.getenv("ECR_REPO_SPARK") or os.getenv("TF_VAR_ecr_repo_spark")
    tag_spark = os.getenv("SPARK_IMAGE_TAG", "latest")
    if repo_spark and not os.getenv("TF_VAR_spark_image"):
        set_tf("spark_image", f"{repo_spark}:{tag_spark}")

    from tools import logger
    logger.info(f"Exported {len([k for k in os.environ if k.startswith('TF_VAR_')])} TF_VARs for env={env}")
    return []
