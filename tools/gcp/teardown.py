"""
GCP Teardown Orchestrator (reference: tools/aws/teardown.py).

Usage:
  python tools/gcp/teardown.py --scope kube --env dev
  python tools/gcp/teardown.py --scope nonkube --env dev
  python tools/gcp/teardown.py --scope all --env dev --non-interactive

Order (matches AWS): scope stacks first (nonkube, kube), then nondurable, durable, durable_with_cooloff.

Pre-destroy:
- kube: k8s_pre_destroy_cleanup (CronJob, Job, LoadBalancer, namespace) before tofu destroy.
- durable: targeted Cloud SQL destroy + poll until instance gone (GCP async 5–15+ min) +
  gcloud compute networks peerings delete (Compute API) + tofu state rm. Avoids Service
  Networking API "Producer services still using" block (40+ min). See durable_pre_destroy.py,
  WAR_STORIES_GCP §8.
"""
import argparse
import os
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.stats import TeardownStats, scope_for
from tools.gcp.scope_shared.core.backend import resolve_region, resolve_state_bucket, gcs_delta_bucket
from tools.cloud_shared.logging import logger

load_dotenv()

ORDER = {
    "kube": ["infra_terraform/live_deploy/gcp/kube"],
    "nonkube": ["infra_terraform/live_deploy/gcp/nonkube"],
    "all": [
        "infra_terraform/live_deploy/gcp/nonkube",
        "infra_terraform/live_deploy/gcp/kube",
        "infra_terraform/live_deploy/gcp/scope_shared/nondurable",
    ],
}


def _destroy_vars_for_stack(stack: str, env: str, region: str) -> list[str]:
    """Build -var=... for tofu destroy. Required so destroy doesn't prompt for variables."""
    prefix = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    gcp_proj = os.getenv("GCP_PROJECT_ID", "")
    bucket = resolve_state_bucket(region)
    base = [f"-var=prefix={prefix}", f"-var=env={env}", f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}"]

    if "nonkube" in stack:
        from tools.gcp.scope_shared.core.resource_names import (
            cloud_run_service,
            spark_job_name,
            artifact_registry_repo_app,
            artifact_registry_repo_spark,
        )
        repo_app = artifact_registry_repo_app(env)
        repo_spark = artifact_registry_repo_spark(env)
        app_img = os.getenv("TF_VAR_app_image") or f"{region}-docker.pkg.dev/{gcp_proj}/{repo_app}/app:latest"
        spark_img = os.getenv("TF_VAR_spark_image") or f"{region}-docker.pkg.dev/{gcp_proj}/{repo_spark}/spark:latest"
        llm_raw = (os.getenv("GCP_LLM_PROVIDER") or os.getenv("LLM_PROVIDER", "gemini")).strip()
        llm_provider = llm_raw.split("#")[0].strip().lower() or "gemini"
        claude_raw = (os.getenv("CLAUDE_MODEL", "") or "claude-3-5-haiku-20241022").strip()
        claude_model = claude_raw.split("#")[0].strip() or "claude-3-5-haiku-20241022"
        return base + [
            f"-var=cloud_run_service_name={cloud_run_service(env, region)}",
            f"-var=spark_job_name={spark_job_name(env, region)}",
            f"-var=app_image={app_img}",
            f"-var=spark_image={spark_img}",
            f"-var=tf_state_bucket={bucket}",
            f"-var=tf_state_prefix={prefix}",
            f"-var=delta_bucket_fallback={gcs_delta_bucket(env, region)}",
            f"-var=llm_provider={llm_provider}",
            f"-var=claude_model={claude_model}",
        ]
    if "kube" in stack and "scope_shared" not in stack:
        from tools.gcp.scope_shared.core.resource_names import gke_cluster
        from tools.gcp.provider_config_handler import get_gke_location, get_initial_node_count
        gke_location = get_gke_location(region)
        zone = gke_location if gke_location != region else None
        return base + [
            f"-var=gke_cluster_name={gke_cluster(env, region, zone=zone)}",
            f"-var=gke_location={gke_location}",
            f"-var=initial_node_count={get_initial_node_count(region)}",
            f"-var=gke_deletion_protection=false",
            f"-var=tf_state_bucket={bucket}",
            f"-var=tf_state_prefix={prefix}",
        ]
    if "nondurable" in stack:
        from tools.gcp.scope_shared.core.resource_names import artifact_registry_repo_app, artifact_registry_repo_spark
        return base + [
            f"-var=gcs_delta_bucket={gcs_delta_bucket(env, region)}",
            f"-var=artifact_registry_repo_app={artifact_registry_repo_app(env)}",
            f"-var=artifact_registry_repo_spark={artifact_registry_repo_spark(env)}",
        ]
    if "durable" in stack and "cooloff" not in stack:
        db_pw = os.getenv("PGPASSWORD", "postgres")
        return base + [
            f"-var=tf_state_bucket={bucket}",
            f"-var=tf_state_prefix={prefix}",
            f"-var=cloud_sql_root_password={db_pw}",
        ]
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    ap.add_argument("--non-interactive", action="store_true")
    ap.add_argument("--incl-dura", action="store_true", help="Include durable (VPC) in teardown (scope=all)")
    ap.add_argument("--incl-dura-all", action="store_true", help="Include durable and durable_with_cooloff (secrets)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    stats = TeardownStats()

    stacks_to_destroy = list(ORDER[args.scope])
    if args.scope == "all" and (args.incl_dura or args.incl_dura_all):
        stacks_to_destroy.append("infra_terraform/live_deploy/gcp/scope_shared/durable")
        if args.incl_dura_all:
            stacks_to_destroy.append("infra_terraform/live_deploy/gcp/scope_shared/durable_with_cooloff")

    for stack in stacks_to_destroy:
        stack_path = os.path.join(repo_root, stack)
        if not os.path.isdir(stack_path):
            continue
        # Pre-destroy kube: remove CronJob, Job, LoadBalancer svc, namespace before tofu destroy.
        # Match kube stack only (not nonkube, which contains "kube" as substring).
        if "scope_shared" not in stack and "kube" in stack and "nonkube" not in stack:
            logger.step("Pre-destroy kube: removing CronJob, Job, LoadBalancer, namespace...")
            try:
                from tools.gcp.kube.kube_pre_destroy import k8s_pre_destroy_cleanup
                k8s_pre_destroy_cleanup(args.env, region, stats=stats)
            except Exception as e:
                logger.warning(f"Pre-destroy kube: {e}")

        stats.set_scope(scope_for(stack))
        from tools.gcp.scope_shared.core.terra_init import init_stack
        from tools.gcp.scope_shared.core.terra_runner import terra
        init_stack(stack_path, args.env, region)
        destroy_vars = _destroy_vars_for_stack(stack, args.env, region)

        # Pre-destroy durable: targeted Cloud SQL destroy + poll until instance gone.
        # GCP deletes Cloud SQL asynchronously; service networking connection delete fails until
        # the instance is fully gone. See durable_pre_destroy.py.
        # Match durable stack only (not nondurable, which contains "durable" as substring).
        if "scope_shared/durable" in stack and "durable_with_cooloff" not in stack:
            from tools.gcp.scope_shared.teardown.durable_pre_destroy import pre_destroy_durable
            pre_destroy_durable(args.env, region, stack_path, destroy_vars, stats=stats)

        logger.step(f"Destroy {stack}...")
        destroy_cmd = ["destroy", "-auto-approve"] if args.non_interactive else ["destroy"]

        # Durable: retry destroy on "Producer services still using connection" (GCP async release).
        if "scope_shared/durable" in stack and "durable_with_cooloff" not in stack:
            from tools.gcp.scope_shared.teardown.durable_pre_destroy import destroy_durable_with_retry
            with stats.timed("Tofu destroy", stack.split("/")[-1]):
                destroy_durable_with_retry(destroy_cmd + destroy_vars, stack_path, region)
        else:
            with stats.timed("Tofu destroy", stack.split("/")[-1]):
                terra(destroy_cmd + destroy_vars, cwd=stack_path, check=False)

    # When durable is included, remove local Docker cache images used by this provider
    if args.scope == "all" and (args.incl_dura or args.incl_dura_all):
        try:
            import subprocess
            from tools.gcp.scope_shared.core.resource_names import (
                artifact_registry_repo_app,
                artifact_registry_repo_spark,
            )
            app_repo = artifact_registry_repo_app(args.env)
            spark_repo = artifact_registry_repo_spark(args.env)
            kube_proxy_repo = f"fru-kube-proxy-img-gcp-{args.env}"
            app_tag = os.getenv("APP_IMAGE_TAG", "latest")
            refs = [f"{app_repo}:latest", f"{spark_repo}:latest", f"{kube_proxy_repo}:latest"]
            if app_tag != "latest":
                refs.extend([f"{app_repo}:{app_tag}", f"{kube_proxy_repo}:{app_tag}"])
            spark_tag = os.getenv("SPARK_IMAGE_TAG", "latest")
            if spark_tag != "latest":
                refs.append(f"{spark_repo}:{spark_tag}")
            for ref in refs:
                subprocess.run(["docker", "rmi", ref], capture_output=True)
            logger.info("Removed local Docker cache images for GCP: %s", ", ".join(refs))
        except Exception as e:
            logger.warning("Local Docker image cleanup (GCP): %s", e)

    stats.print_summary()
    logger.success("Teardown complete.")


if __name__ == "__main__":
    main()
