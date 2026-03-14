"""
Nonkube-specific deploy logic: ECS apply, frontend deploy, ECS bootstrap.

Called by deploy.py when scope is nonkube or all (nonkube first when scope=all).
"""
import os

from tools.aws.provider_config_handler import get_nonkube_compute_config
from tools.cloud_shared.analytics_schedule import get_required_analytics_scheduler_interval_seconds
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.import_preexist.nonkube import run_import_nonkube
from tools.cloud_shared.stats import DeployStats, scope_for
from tools.aws.scope_shared.deploy.deploy_common import (
    apply_stack_nonkube_with_ecs_import_retry,
    plan_shows_no_changes,
    tofu_output_json,
    run_ecs_bootstrap,
)
from tools.aws.scope_shared.deploy.deploy_frontend import (
    deploy_frontend_to_s3,
    invalidate_cloudfront,
    wait_for_invalidation,
)


def run_deploy_nonkube(
    env: str,
    region: str,
    snd: dict,
    app_image_full: str,
    spark_image_full: str,
    args,
    stats: DeployStats | None = None,
) -> None:
    """
    Deploy nonkube stack: ECS apply, frontend, ECS bootstrap.
    Idempotent and safe to re-run.
    """
    # Set ECS compute vars from config (min/max, task cpu/memory)
    cfg = get_nonkube_compute_config(region)
    tasks = cfg["tasks"]
    os.environ["TF_VAR_min_instance_count"] = str(cfg["min_instance_count"])
    os.environ["TF_VAR_max_instance_count"] = str(cfg["max_instance_count"])
    os.environ["TF_VAR_api_task_cpu"] = str(tasks["api"]["cpu"])
    os.environ["TF_VAR_api_task_memory"] = str(tasks["api"]["memory"])
    os.environ["TF_VAR_spark_task_cpu"] = str(tasks["spark"]["cpu"])
    os.environ["TF_VAR_spark_task_memory"] = str(tasks["spark"]["memory"])

    scope_label = scope_for("infra_terraform/live_deploy/aws/nonkube")
    if stats:
        stats.set_scope(scope_label)

    # Fail-fast: require ANALYTICS_SCHEDULER_INTERVAL_SECONDS (single source of truth for EventBridge schedule)
    get_required_analytics_scheduler_interval_seconds()

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Phase 8.5: Import pre-existing resources (state/reality reconciliation)
    # DEPLOYMENT_OPTIMIZATION §2.3: Skip import when plan shows no changes (state clean).
    nonkube_stack = "infra_terraform/live_deploy/aws/nonkube"
    plan_vars = [
        "-var", f"app_image={app_image_full}",
        "-var", f"spark_image={spark_image_full}",
    ]
    img_tags = os.getenv("CONTAINER_IMAGE_TAGS", "")
    if img_tags:
        plan_vars += ["-var", f"app_image_tags={img_tags}"]

    plan_clean = False  # set after init

    def _import_preexist():
        nonlocal plan_clean
        init_stack(nonkube_stack, env, region)
        get_base_vars(env, region)
        plan_clean = plan_shows_no_changes(nonkube_stack, env, region, plan_vars)
        if plan_clean:
            logger.info("[Import] Skipping nonkube: plan shows no changes (state clean)")
            return
        logger.info("[Import] Reconciling state with AWS (broader import for deploy convenience)")
        failed = run_import_nonkube(
            nonkube_stack,
            env,
            region,
            prefix=(os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")),
        )
        if failed > 0:
            raise SystemExit(
                f"Import failed for {failed} resource(s). Fix state (run import manually) and retry. "
                "See tools/aws/scope_shared/import_preexist/run_import.py --scope nonkube"
            )
    _timed("Import pre-existing", "nonkube", _import_preexist)

    # Phase 9: Apply ECS stack (skip when plan showed no changes — §2.3)
    def _apply_ecs():
        if plan_clean:
            logger.info("[Nonkube] Skipping tofu apply: plan showed no changes (state clean)")
            return
        extra = [
            "-var", f"app_image={app_image_full}",
            "-var", f"spark_image={spark_image_full}",
        ]
        img_tags = os.getenv("CONTAINER_IMAGE_TAGS", "")
        if img_tags:
            extra += ["-var", f"app_image_tags={img_tags}"]
        apply_stack_nonkube_with_ecs_import_retry(
            nonkube_stack,
            env,
            extra,
            region,
        )

    _timed("Tofu apply", "infra_terraform/live_deploy/aws/nonkube", _apply_ecs)

    # Deploy frontend to S3
    stack_out = tofu_output_json("infra_terraform/live_deploy/aws/nonkube", env, region)
    frontend_bucket = stack_out.get("frontend_s3_bucket_id", {}).get("value")
    if frontend_bucket:
        deploy_frontend_to_s3(frontend_bucket, env, scope="nonkube")
        cf_dist_id = stack_out.get("cloudfront_distribution_id", {}).get("value")
        if cf_dist_id:
            ok, inv_id = invalidate_cloudfront(cf_dist_id, region)
            if ok and inv_id:
                if not wait_for_invalidation(cf_dist_id, inv_id, timeout_minutes=15, non_blocking=True, region=region):
                    logger.warning("[CloudFront Invalidation] Did not complete within timeout; deployment continues.")
        else:
            logger.warning("[CloudFront Invalidation] Skipped: cloudfront_distribution_id not in nonkube stack output")
    else:
        logger.warning("frontend_s3_bucket_id not found; skipping frontend deploy")

    # Phase 10: ECS bootstrap
    def _ecs_bootstrap():
        run_ecs_bootstrap(env, region)

    _timed("ECS bootstrap", "run_analytics one-off", _ecs_bootstrap)
    logger.success("ECS bootstrap complete")
