"""
Kube-specific deploy logic: EKS apply, kube_apply bootstrap + schedule, LB wiring, frontend.

Called by deploy.py when scope is kube or all (after nonkube when scope=all).
"""
import os
import subprocess
import time

from tools.cloud_shared.env import require
from tools.cloud_shared.logging import logger
from tools.cloud_shared.stats import DeployStats, scope_for
from tools.aws.common.deploy.deploy_common import (
    apply_stack,
    tofu_output_json,
    upload_csv_to_delta_bucket,
)
from tools.aws.common.deploy.deploy_frontend import (
    deploy_frontend_to_s3,
    invalidate_cloudfront,
    wait_for_invalidation,
)
from tools.aws.common.deploy.bootstrap_helpers import (
    K8S_NAMESPACE,
    wait_for_dns_resolvable,
    wait_for_fru_api_ready,
    verify_api_db_connected,
    k8s_rollout_restart_api,
)


def run_deploy_kube(
    env: str,
    region: str,
    snd: dict,
    app_image_full: str,
    spark_image_full: str,
    args,
    stats: DeployStats | None = None,
) -> None:
    """
    Deploy kube stack: EKS apply, kube_apply bootstrap+schedule, LB wiring, frontend.
    Idempotent and safe to re-run.
    """
    scope_label = scope_for("live_deploy_aws/kube")
    if stats:
        stats.set_scope(scope_label)

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Phase 9: Apply EKS stack
    def _apply_eks():
        apply_stack(
            "live_deploy_aws/kube",
            env,
            [
                "-var", f"eks_instance_types=[\"{require('EKS_NODE_INSTANCE_TYPES')}\"]",
                "-var", f"eks_desired_nodes={require('EKS_DESIRED_NODES')}",
            ],
            region,
        )

    _timed("Tofu apply", "live_deploy_aws/kube", _apply_eks)

    # Phase 10: K8s bootstrap + schedule
    delta_bucket = snd["delta_bucket"]["value"]
    csv_uploaded = upload_csv_to_delta_bucket(delta_bucket, region)
    durable = tofu_output_json("live_deploy_aws/scope_shared/durable", env, region)
    aurora_endpoint = durable.get("aurora_endpoint", {}).get("value", "")
    db_secret_arn = durable.get("db_password_plain_secret_arn", {}).get("value", "")
    openai_secret_arn = durable.get("openai_api_key_secret_arn", {}).get("value", "")
    delta_table_path = f"s3a://{delta_bucket}/delta/fru_sales"

    kube_apply_args = [
        "python", "tools/aws/kube/kube_apply.py", "--env", env, "--region", region, "--phase", "bootstrap",
        "--spark-image", spark_image_full, "--app-image", app_image_full,
        "--delta-bucket", delta_bucket,
        "--pg-host", aurora_endpoint or "localhost",
        "--pg-port", str(durable.get("aurora_port", {}).get("value", 5432)),
        "--pg-database", durable.get("aurora_database_name", {}).get("value", "fru_db"),
        "--pg-user", "postgres",
        "--aws-region", region,
        "--delta-table-path", delta_table_path,
    ]
    if db_secret_arn:
        kube_apply_args += ["--db-secret-arn", db_secret_arn]
    if openai_secret_arn:
        kube_apply_args += ["--openai-secret-arn", openai_secret_arn]
    bedrock_profile = os.getenv("AWS_BEDROCK_INFERENCE_PROFILE_ID", "")
    bedrock_model = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")
    if bedrock_profile:
        kube_apply_args += ["--bedrock-inference-profile-id", bedrock_profile]
    if bedrock_model:
        kube_apply_args += ["--bedrock-model-id", bedrock_model]
    if csv_uploaded:
        kube_apply_args += ["--force"]

    def _kube_bootstrap():
        subprocess.run(kube_apply_args, check=True)
        subprocess.run([
            "python", "tools/aws/kube/kube_apply.py", "--env", env, "--region", region, "--phase", "schedule",
            "--spark-image", spark_image_full, "--delta-bucket", delta_bucket,
            "--pg-host", aurora_endpoint or "localhost",
            "--pg-port", str(durable.get("aurora_port", {}).get("value", 5432)),
            "--pg-database", durable.get("aurora_database_name", {}).get("value", "fru_db"),
            "--pg-user", "postgres",
            "--delta-table-path", delta_table_path,
        ], check=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region})

    _timed("K8s bootstrap + schedule", "kube_apply bootstrap+schedule", _kube_bootstrap)

    # War Story 44: Restart pods so they pick up updated db-credentials
    k8s_rollout_restart_api(env, region=region)

    logger.step("Waiting for fru-api pods to be ready...")
    wait_for_fru_api_ready(env, timeout_seconds=600, check_interval_seconds=15, region=region)
    logger.success("fru-api pods ready")

    # Wire K8s LoadBalancer into CloudFront API origin
    lb_host = ""
    for attempt in range(18):
        try:
            lb_host = subprocess.check_output([
                "kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}",
            ], text=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region}).strip()
            if lb_host:
                break
        except Exception:
            pass
        if attempt < 17:
            time.sleep(10)

    if lb_host:
        wait_for_dns_resolvable(lb_host, timeout_seconds=120, check_interval_sec=5, heartbeat_interval_sec=30)
        verify_api_db_connected(f"http://{lb_host}", timeout_seconds=60)
        logger.step("Re-applying kube stack with LoadBalancer hostname for CloudFront API origin...")

        def _reapply_kube():
            apply_stack(
                "live_deploy_aws/kube",
                env,
                [
                    "-var", f"eks_instance_types=[\"{require('EKS_NODE_INSTANCE_TYPES')}\"]",
                    "-var", f"eks_desired_nodes={require('EKS_DESIRED_NODES')}",
                    "-var", f"ingress_hostname={lb_host}",
                ],
                region,
            )

        _timed("Tofu apply (ingress)", "live_deploy_aws/kube (ingress_hostname)", _reapply_kube)
        logger.success("CloudFront API origin wired to K8s LoadBalancer")
    else:
        logger.warning("LoadBalancer hostname not available; CloudFront API routes may not work until re-applied manually")

    # Deploy frontend to S3
    try:
        stack_out = tofu_output_json("live_deploy_aws/kube", env, region)
        frontend_bucket = stack_out.get("frontend_s3_bucket_id", {}).get("value")
        if frontend_bucket:
            deploy_frontend_to_s3(frontend_bucket, env)
            cf_dist_id = stack_out.get("cloudfront_distribution_id", {}).get("value")
            if cf_dist_id:
                ok, inv_id = invalidate_cloudfront(cf_dist_id, region)
                if ok and inv_id:
                    if not wait_for_invalidation(cf_dist_id, inv_id, timeout_minutes=15, non_blocking=True, region=region):
                        logger.warning("[CloudFront Invalidation] Did not complete within timeout; deployment continues.")
            else:
                logger.warning("[CloudFront Invalidation] Skipped: cloudfront_distribution_id not in kube stack output")
        else:
            logger.warning("frontend_s3_bucket_id not found; skipping kube frontend deploy")
    except Exception as e:
        logger.warning(f"Could not deploy kube frontend: {e}")
