#!/usr/bin/env python3
"""
Fix DB credentials for an already-deployed kube stack (no full deploy).

Use when /analytics returns "Database not configured" or /query/stream returns
"Agent-based query processing is disabled" due to Aurora vs K8s secret mismatch.

Steps:
  1. ensure_secrets (sync PGPASSWORD from .env to Secrets Manager)
  2. kube_apply bootstrap --force (refresh K8s db-credentials from Secrets Manager)
  3. rollout restart (pods pick up new secret)

Usage:
  python tools/aws/temp-one-off/fix_kube_db_credentials.py --env dev
"""
import argparse
import os
import subprocess

from tools.cloud_shared.env import load_dotenv
from tools.aws.common.core.backend import resolve_region
from tools.aws.common.deploy.bootstrap_helpers import k8s_rollout_restart_api, wait_for_fru_api_ready
from tools.cloud_shared.logging import logger

load_dotenv()


def main():
    ap = argparse.ArgumentParser(description="Fix kube DB credentials without full deploy")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    args = ap.parse_args()

    if not os.getenv("PGPASSWORD"):
        logger.error("PGPASSWORD must be set in .env")
        raise SystemExit(1)

    region = resolve_region(args.region)
    env_vars = {**os.environ, "CLOUD_REGION": region, "AWS_REGION": region}

    logger.step("1. Ensuring secrets in Secrets Manager...")
    subprocess.run(
        ["python", "tools/aws/common/deploy/ensure_secrets.py", "--env", args.env, "--region", region],
        check=True,
        env=env_vars,
    )
    logger.success("Secrets ensured")

    logger.step("2. Refreshing K8s db-credentials (bootstrap --force)...")
    from tools.aws.common.deploy.deploy_common import init_stack, tofu_output_json
    init_stack("live-deploy-aws/scope-shared/durable", args.env, region)
    init_stack("live-deploy-aws/scope-shared/nondurable", args.env, region)
    from tools.aws.terra_var_handling import get_base_vars
    get_base_vars(args.env, region)
    outputs = tofu_output_json("live-deploy-aws/scope-shared/durable", args.env, region)
    aurora_endpoint = outputs.get("aurora_endpoint", {}).get("value", "")
    db_secret_arn = outputs.get("db_password_plain_secret_arn", {}).get("value", "")
    openai_secret_arn = outputs.get("openai_api_key_secret_arn", {}).get("value", "")

    snd_out = tofu_output_json("live-deploy-aws/scope-shared/nondurable", args.env, region)
    delta_bucket = snd_out.get("delta_bucket", {}).get("value", "")
    app_repo = snd_out.get("ecr_app_url", {}).get("value", "")
    spark_repo = snd_out.get("ecr_spark_url", {}).get("value", "")
    app_image = f"{app_repo}:{os.getenv('APP_IMAGE_TAG', 'latest')}"
    spark_image = f"{spark_repo}:{os.getenv('SPARK_IMAGE_TAG', 'latest')}"
    delta_table_path = f"s3a://{delta_bucket}/delta/fru_sales"

    kube_args = [
        "python", "tools/aws/kube/kube_apply.py", "--env", args.env, "--region", region, "--phase", "bootstrap",
        "--spark-image", spark_image, "--app-image", app_image,
        "--delta-bucket", delta_bucket,
        "--pg-host", aurora_endpoint or "localhost",
        "--pg-port", str(outputs.get("aurora_port", {}).get("value", 5432)),
        "--pg-database", outputs.get("aurora_database_name", {}).get("value", "fru_db"),
        "--pg-user", "postgres",
        "--aws-region", region,
        "--delta-table-path", delta_table_path,
        "--force",
    ]
    if db_secret_arn:
        kube_args += ["--db-secret-arn", db_secret_arn]
    if openai_secret_arn:
        kube_args += ["--openai-secret-arn", openai_secret_arn]
    bedrock_profile = os.getenv("AWS_BEDROCK_INFERENCE_PROFILE_ID", "")
    bedrock_model = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")
    if bedrock_profile:
        kube_args += ["--bedrock-inference-profile-id", bedrock_profile]
    if bedrock_model:
        kube_args += ["--bedrock-model-id", bedrock_model]
    subprocess.run(kube_args, check=True, env=env_vars)
    logger.success("K8s db-credentials refreshed")

    logger.step("3. Restarting fru-api pods...")
    k8s_rollout_restart_api(args.env, region=region)
    logger.success("Rollout restart triggered")

    logger.step("4. Waiting for pods to be ready...")
    wait_for_fru_api_ready(args.env, timeout_seconds=300, check_interval_seconds=10, region=region)
    logger.success("Pods ready")

    logger.success("\n✓ DB credentials fix complete. /analytics and /query/stream should work now.")


if __name__ == "__main__":
    main()
