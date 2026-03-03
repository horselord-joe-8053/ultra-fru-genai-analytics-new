"""
Nonkube-specific deploy logic: Cloud Run + Spark apply + analytics bootstrap.

Called by deploy.py when scope is nonkube or all (nonkube first when scope=all).
After apply: runs analytics bootstrap (one-off run_analytics) so /analytics has data immediately.
"""
import os
from typing import TYPE_CHECKING

from tools.cloud_shared.logging import logger
from tools.gcp.scope_shared.core.backend import resolve_state_bucket, gcs_delta_bucket
from tools.gcp.scope_shared.core.resource_names import (
    cloud_run_service,
    spark_job_name,
    artifact_registry_repo_app,
    artifact_registry_repo_spark,
)
from tools.gcp.scope_shared.deploy.deploy_common import run_deploy_stack

if TYPE_CHECKING:
    from tools.cloud_shared.stats import DeployStats


def run_deploy_nonkube(
    repo_root: str,
    env: str,
    region: str,
    prefix: str,
    gcp_proj: str,
    args,
    stats: "DeployStats | None" = None,
) -> bool:
    """Deploy nonkube stack (Cloud Run + frontend). Returns True if plan succeeded."""
    stack_path = os.path.join(repo_root, "infra_terraform/live_deploy/gcp/nonkube")
    bucket = resolve_state_bucket(region)
    delta_bucket = gcs_delta_bucket(env, region)
    repo_app = artifact_registry_repo_app(env)
    repo_spark = artifact_registry_repo_spark(env)

    # Fail-fast: require real Artifact Registry images. No placeholder to avoid hiding config errors.
    if not gcp_proj:
        raise ValueError("GCP_PROJECT_ID required for app/spark image resolution")
    _app_img = f"{region}-docker.pkg.dev/{gcp_proj}/{repo_app}/app:latest"
    _spark_img = f"{region}-docker.pkg.dev/{gcp_proj}/{repo_spark}/spark:latest"
    app_img = os.getenv("TF_VAR_app_image") or _app_img
    spark_img = os.getenv("TF_VAR_spark_image") or _spark_img

    llm_provider = os.getenv("GCP_LLM_PROVIDER") or os.getenv("LLM_PROVIDER", "gemini")
    llm_provider = llm_provider.strip().lower()
    claude_model = os.getenv("CLAUDE_MODEL", "").strip() or "claude-3-5-haiku-20241022"
    plan_vars = [
        f"-var=prefix={prefix}", f"-var=env={env}",
        f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
        f"-var=cloud_run_service_name={cloud_run_service(env, region)}",
        f"-var=spark_job_name={spark_job_name(env, region)}",
        f"-var=app_image={app_img}", f"-var=spark_image={spark_img}",
        f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
        f"-var=delta_bucket_fallback={delta_bucket}",
        f"-var=llm_provider={llm_provider}",
        f"-var=claude_model={claude_model}",
    ]

    def _apply():
        logger.info("Applying nonkube stack (Cloud Run + Spark + frontend CDN)...")
        return run_deploy_stack(stack_path, plan_vars, region, env, args.apply)

    if stats:
        with stats.timed("Tofu apply", "nonkube"):
            ok = _apply()
    else:
        ok = _apply()

    if ok and args.apply:
        from tools.gcp.scope_shared.deploy.analytics_bootstrap import run_analytics_bootstrap
        logger.step("Running analytics bootstrap (one-off run_analytics)...")
        if stats:
            with stats.timed("Bootstrap", "analytics_bootstrap"):
                run_analytics_bootstrap(env, region, force=getattr(args, "force_refresh_data", False))
        else:
            run_analytics_bootstrap(env, region, force=getattr(args, "force_refresh_data", False))
        logger.success("Analytics bootstrap complete")

        # Deploy frontend to GCS (Cloud CDN serves from this bucket)
        from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json
        from tools.gcp.scope_shared.deploy.deploy_frontend import (
            deploy_frontend_to_gcs,
            invalidate_cloud_cdn,
        )
        try:
            logger.info("Fetching nonkube outputs for frontend deploy...")
            nonkube_out = get_tofu_output_json(
                "infra_terraform/live_deploy/gcp/nonkube", env, region, "nonkube"
            )
            frontend_bucket = nonkube_out.get("frontend_bucket_name", {}).get("value")
            if frontend_bucket:
                deploy_frontend_to_gcs(frontend_bucket, env, scope="nonkube", project_id=gcp_proj)
                url_map = nonkube_out.get("url_map_name", {}).get("value")
                if url_map and gcp_proj:
                    invalidate_cloud_cdn(url_map, gcp_proj)
            else:
                logger.warning("frontend_bucket_name not in nonkube outputs; skipping nonkube frontend deploy")
        except Exception as e:
            logger.warning(
                "Could not deploy nonkube frontend: %s. Frontend may be stale; re-run deploy to sync.",
                e,
            )

    return ok
