import os

from tools.aws.scope_shared.core import resource_names
from tools.cloud_shared.analytics_schedule import seconds_to_eventbridge_rate
from tools.cloud_shared.env import require

# Map .env keys to Terraform variable names.
# Resource names (delta_bucket, ecs_cluster_name, etc.) are built via resource_names.py
# from PROJ_PREFIX + *_COMPONENT vars; legacy full-name vars supported during transition.
MAP = {
    "FRU_ENV": "env",
    "CLOUD_REGION": "aws_region",
    "VPC_CIDR": "vpc_cidr",
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
    "AWS_BEDROCK_REGION": "bedrock_region",
}

def get_base_vars(env: str, region: str | None = None):
    """
    Set TF_VAR_ environment variables for OpenTofu/Terraform.
    Returns an empty list to maintain compatibility with existing script signatures.
    Resource names built via resource_names.py (PROJ_PREFIX + *_COMPONENT convention).
    """
    if region:
        os.environ["CLOUD_REGION"] = region

    from tools.aws.scope_shared.core.backend import (
        resolve_region,
        resolve_state_bucket,
        resolve_state_lock_table,
        resolve_bucket_region,
    )
    deploy_region = region or resolve_region(None)

    # helper to set TF_VAR
    def set_tf(name, val):
        os.environ[f"TF_VAR_{name}"] = str(val)

    set_tf("env", env)
    set_tf("prefix", resource_names.get_proj_prefix())

    # TF State Prefix (same as project prefix for state key path)
    tf_state_prefix = os.getenv("TF_STATE_PREFIX") or resource_names.get_proj_prefix()
    set_tf("tf_state_prefix", tf_state_prefix)

    # Map non-resource vars from env
    for env_key, tf_key in MAP.items():
        val = os.getenv(env_key)
        if val:
            set_tf(tf_key, val)

    # Derive spark_schedule_expression from ANALYTICS_SCHEDULER_INTERVAL_SECONDS when set
    # (deploy_nonkube requires it before apply; MAP above sets analytics_scheduler_interval_seconds)
    val = os.getenv("ANALYTICS_SCHEDULER_INTERVAL_SECONDS")
    if val:
        try:
            n = int(val)
            if n >= 60:
                set_tf("analytics_scheduler_interval_seconds", n)
                set_tf("spark_schedule_expression", seconds_to_eventbridge_rate(n))
        except ValueError:
            pass

    # CRITICAL: Ensure aws_region is explicitly set
    if not os.getenv("TF_VAR_aws_region"):
        set_tf("aws_region", deploy_region)

    # State bucket and lock table
    bucket = resolve_state_bucket(deploy_region)
    set_tf("tf_state_bucket", bucket)
    set_tf("tf_state_bucket_region", resolve_bucket_region(bucket))
    lock_table = resolve_state_lock_table(deploy_region)
    if lock_table:
        set_tf("tf_lock_table", lock_table)

    # Resource names via resource_names.py (PROJ_PREFIX + *_COMPONENT)
    container_type = os.getenv("CONTAINER_TYPE", "")
    set_tf("ecs_cluster_name", resource_names.ecs_cluster(env, deploy_region))
    eks_name = resource_names.eks_cluster(env, deploy_region)
    set_tf("eks_cluster_name", eks_name)
    set_tf("alb_name", resource_names.alb_name(env, deploy_region))
    set_tf("delta_bucket", resource_names.s3_delta_bucket(env, deploy_region))
    set_tf("artifacts_bucket", resource_names.s3_artifacts_bucket(env, deploy_region))
    set_tf("ecr_repo_app", resource_names.ecr_repo_app(env, deploy_region, container_type=container_type))
    set_tf("ecr_repo_spark", resource_names.ecr_repo_spark(env, deploy_region, container_type=container_type))

    # CloudWatch log groups (path-style; for Terraform when vars added)
    set_tf("cloudwatch_log_group_spark", resource_names.log_group_spark(env, deploy_region))
    set_tf("cloudwatch_log_group_ecs_api", resource_names.log_group_ecs_api(env, deploy_region))

    # Construct full images
    repo_app = os.getenv("TF_VAR_ecr_repo_app")
    tag_app = os.getenv("APP_IMAGE_TAG", "latest")
    if repo_app and not os.getenv("TF_VAR_app_image"):
        set_tf("app_image", f"{repo_app}:{tag_app}")

    repo_spark = os.getenv("TF_VAR_ecr_repo_spark")
    tag_spark = os.getenv("SPARK_IMAGE_TAG", "latest")
    if repo_spark and not os.getenv("TF_VAR_spark_image"):
        set_tf("spark_image", f"{repo_spark}:{tag_spark}")

    from tools.cloud_shared.logging import logger
    logger.info(f"Exported {len([k for k in os.environ if k.startswith('TF_VAR_')])} TF_VARs for env={env}")
    return []
