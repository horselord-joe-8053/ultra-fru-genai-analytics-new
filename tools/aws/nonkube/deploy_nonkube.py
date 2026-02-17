"""
Nonkube-specific deploy logic: ECS apply, frontend deploy, ECS bootstrap.

Called by deploy.py when scope is nonkube or all (nonkube first when scope=all).
"""
from tools._env import require
from tools.common.logging import logger
from tools.common.stats import DeployStats, scope_for
from tools.aws.common.deploy.deploy_common import (
    apply_stack_nonkube_with_ecs_import_retry,
    tofu_output_json,
    upload_csv_to_delta_bucket,
    clear_delta_table,
    run_ecs_bootstrap,
)
from tools.aws.common.deploy.deploy_frontend import (
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
    scope_label = scope_for("live-deploy-aws/nonkube")
    if stats:
        stats.set_scope(scope_label)

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Phase 9: Apply ECS stack
    app_repo_url = snd["ecr_app_url"]["value"]

    def _apply_ecs():
        apply_stack_nonkube_with_ecs_import_retry(
            "live-deploy-aws/nonkube",
            env,
            [
                "-var", f"app_image={app_repo_url}:{require('APP_IMAGE_TAG')}",
                "-var", f"spark_image={spark_image_full}",
            ],
            region,
        )

    _timed("Tofu apply", "live-deploy-aws/nonkube", _apply_ecs)

    # Deploy frontend to S3
    stack_out = tofu_output_json("live-deploy-aws/nonkube", env, region)
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
            logger.warning("[CloudFront Invalidation] Skipped: cloudfront_distribution_id not in nonkube stack output")
    else:
        logger.warning("frontend_s3_bucket_id not found; skipping frontend deploy")

    # Phase 10: ECS bootstrap
    delta_bucket = snd.get("delta_bucket", {}).get("value", "")
    csv_uploaded = False
    if delta_bucket:
        csv_uploaded = upload_csv_to_delta_bucket(delta_bucket, region)
        if csv_uploaded:
            clear_delta_table(delta_bucket, region)

    def _ecs_bootstrap():
        run_ecs_bootstrap(env, region, force=csv_uploaded)

    _timed("ECS bootstrap", "run_analytics one-off", _ecs_bootstrap)
    logger.success("ECS bootstrap complete")
