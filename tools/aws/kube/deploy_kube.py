"""
Kube-specific deploy logic: EKS apply, kube_apply bootstrap + schedule, LB wiring, frontend.

Called by deploy.py when scope is kube or all (after nonkube when scope=all).
"""
import os
import subprocess
import sys
import time

from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.import_preexist.kube import run_import_kube
from tools.cloud_shared.stats import DeployStats, scope_for
from tools.aws.scope_shared.deploy.deploy_common import (
    apply_stack,
    plan_shows_no_changes,
    tofu_output_json,
)
from tools.aws.scope_shared.deploy.deploy_frontend import (
    deploy_frontend_to_s3,
    invalidate_cloudfront,
    wait_for_invalidation,
)
from tools.aws.scope_shared.deploy.bootstrap_helpers import (
    K8S_NAMESPACE,
    wait_for_dns_resolvable,
    wait_for_fru_api_ready,
    verify_api_db_connected,
    k8s_rollout_restart_api,
)


def _try_get_lb_hostname(env: str, region: str) -> str:
    """Try to get LB hostname from kubectl (re-deploy: LB usually already exists). Returns empty if not found.
    Current: Classic ELB (in-tree). With aws-load-balancer-type annotation: NLB (AWS Load Balancer Controller)."""
    try:
        out = subprocess.check_output(
            [
                "kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}",
            ],
            text=True,
            env={**os.environ, "CLOUD_REGION": region},
            timeout=10,
        )
        hostname = (out or "").strip()
        if not hostname:
            return ""
        # Reject hostname from a different region (kubectl context may point at another region's cluster)
        # LB hostnames (Classic or NLB): xxx.us-east-1.elb.amazonaws.com
        if f".{region}." not in hostname and f"{region}.elb.amazonaws.com" not in hostname:
            return ""
        return hostname
    except Exception:
        return ""


def _poll_lb_hostname(env: str, region: str, max_attempts: int = 18, interval_sec: int = 10) -> str:
    """Poll kubectl for LB hostname until available or max_attempts. Returns empty if not found."""
    for attempt in range(max_attempts):
        hostname = _try_get_lb_hostname(env, region)
        if hostname:
            return hostname
        if attempt < max_attempts - 1:
            time.sleep(interval_sec)
    return ""


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
    scope_label = scope_for("infra_terraform/live_deploy/aws/kube")
    if stats:
        stats.set_scope(scope_label)

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Phase 8.5: Import pre-existing resources (state/reality reconciliation)
    # DEPLOYMENT_OPTIMIZATION §2.3: Skip import and apply when plan shows no changes (state clean).
    kube_stack = "infra_terraform/live_deploy/aws/kube"
    hostname_before_first_apply = _try_get_lb_hostname(env, region)
    if hostname_before_first_apply:
        logger.info(f"[Kube] LB hostname known before apply: {hostname_before_first_apply}; single apply (skip second)")
    plan_vars: list[str] = []
    if hostname_before_first_apply:
        plan_vars.append("-var")
        plan_vars.append(f"ingress_hostname={hostname_before_first_apply}")

    plan_clean = False  # set after init

    def _import_preexist():
        nonlocal plan_clean
        init_stack(kube_stack, env, region)
        get_base_vars(env, region)
        plan_clean = plan_shows_no_changes(kube_stack, env, region, plan_vars)
        if plan_clean:
            logger.info("[Import] Skipping kube: plan shows no changes (state clean)")
            return
        logger.info("[Import] Reconciling state with AWS (broader import for deploy convenience)")
        from tools.aws.scope_shared.core import resource_names
        eks_cluster_name = resource_names.eks_cluster(env, region)
        failed = run_import_kube(
            kube_stack,
            env,
            region,
            prefix=resource_names.get_proj_prefix(),
            eks_cluster_name=eks_cluster_name,
        )
        if failed > 0:
            raise SystemExit(
                f"Import failed for {failed} resource(s). Fix state (run import manually) and retry. "
                "See tools/aws/scope_shared/import_preexist/run_import.py --scope kube"
            )
    _timed("Import pre-existing", "kube", _import_preexist)

    # Phase 9: Apply EKS stack (skip when plan showed no changes — §2.3)
    def _apply_eks():
        if plan_clean:
            logger.info("[Kube] Skipping tofu apply: plan showed no changes (state clean)")
            return
        extra_vars: list[str] = []
        if hostname_before_first_apply:
            extra_vars += ["-var", f"ingress_hostname={hostname_before_first_apply}"]
        apply_stack(kube_stack, env, extra_vars, region)

    _timed("Tofu apply", "infra_terraform/live_deploy/aws/kube", _apply_eks)

    # Phase 9.5: Install AWS Load Balancer Controller (NLB track only; skip when --elb)
    if not getattr(args, "elb", False):
        def _install_nlb():
            subprocess.run(
                [
                    sys.executable,
                    "tools/aws/kube/install_aws_load_balancer_controller.py",
                    "--env", env,
                    "--region", region,
                ],
                check=True,
                env={**os.environ, "CLOUD_REGION": region},
            )
        _timed("Install NLB controller", "install_aws_load_balancer_controller", _install_nlb)

    # Phase 10: K8s bootstrap + schedule
    delta_bucket = snd["delta_bucket"]["value"]
    durable = tofu_output_json("infra_terraform/live_deploy/aws/scope_shared/durable", env, region)
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
    if getattr(args, "elb", False):
        kube_apply_args += ["--elb"]
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
        ], check=True, env={**os.environ, "CLOUD_REGION": region})

    _timed("K8s bootstrap + schedule", "kube_apply bootstrap+schedule", _kube_bootstrap)

    # War Story 44: Restart pods so they pick up updated db-credentials
    k8s_rollout_restart_api(env, region=region)

    logger.step("Waiting for fru-api pods to be ready...")
    wait_for_fru_api_ready(env, timeout_seconds=600, check_interval_seconds=15, region=region)
    logger.success("fru-api pods ready")

    # Wire K8s LoadBalancer into CloudFront API origin
    # DEPLOYMENT_OPTIMIZATION §2.2: Second apply when (a) we got hostname from poll (didn't have before first apply),
    # or (b) hostname changed after kube_apply (e.g. AWS Load Balancer Controller created NLB, replacing Classic ELB).
    hostname_after_poll = _poll_lb_hostname(env, region)
    hostname_to_use = hostname_after_poll or hostname_before_first_apply
    need_second_apply = hostname_to_use and (
        not hostname_before_first_apply
        or (hostname_after_poll and hostname_after_poll != hostname_before_first_apply)
    )

    if hostname_to_use:
        wait_for_dns_resolvable(hostname_to_use, timeout_seconds=120, check_interval_sec=5, heartbeat_interval_sec=30)
        # LB target health checks can take 2-5 min; allow more retries
        verify_api_db_connected(f"http://{hostname_to_use}", timeout_seconds=60, max_retries=12)

    if need_second_apply:
        logger.step("Re-applying kube stack with LoadBalancer hostname for CloudFront API origin...")

        def _reapply_kube():
            apply_stack(
                "infra_terraform/live_deploy/aws/kube",
                env,
                ["-var", f"ingress_hostname={hostname_to_use}"],
                region,
            )

        _timed("Tofu apply (ingress)", "infra_terraform/live_deploy/aws/kube (ingress_hostname)", _reapply_kube)
        logger.success("CloudFront API origin wired to K8s LoadBalancer")
    elif hostname_to_use and hostname_to_use == hostname_before_first_apply:
        logger.success("CloudFront API origin already wired (hostname unchanged)")
    elif not hostname_to_use:
        logger.warning("LoadBalancer hostname not available; CloudFront API routes may not work until re-applied manually")

    # Deploy frontend to S3
    try:
        stack_out = tofu_output_json("infra_terraform/live_deploy/aws/kube", env, region)
        frontend_bucket = stack_out.get("frontend_s3_bucket_id", {}).get("value")
        if frontend_bucket:
            deploy_frontend_to_s3(frontend_bucket, env, scope="kube")
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
