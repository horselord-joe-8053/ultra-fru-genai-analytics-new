"""
Kube-specific deploy logic: GKE apply.

Called by deploy.py when scope is kube or all (after nonkube when scope=all).
"""
import os
from typing import TYPE_CHECKING

from tools.cloud_shared.logging import logger
from tools.gcp.provider_config_handler import get_gke_location, get_initial_node_count
from tools.gcp.scope_shared.core.backend import resolve_state_bucket
from tools.gcp.scope_shared.core.resource_names import gke_cluster
from tools.gcp.scope_shared.deploy.deploy_common import run_deploy_stack

if TYPE_CHECKING:
    from tools.cloud_shared.stats import DeployStats


def _run_gke_deletion_protection_migration(
    repo_root: str, env: str, region: str, prefix: str, gcp_proj: str, bucket: str
) -> None:
    """One-off apply to set deletion_protection=false on existing regional GKE cluster (before migrating to zonal)."""
    stack_path = os.path.join(repo_root, "infra_terraform/live_deploy/gcp/kube")
    if not os.path.isdir(stack_path):
        return
    os.environ["FRU_ENV"] = env
    from tools.gcp.scope_shared.core.terra_init import init_stack
    from tools.gcp.scope_shared.core.terra_runner import terra
    from tools.gcp.scope_shared.deploy.deploy_common import apply_stack_with_plan

    init_stack(stack_path, env, region)
    untaint = terra(["untaint", "module.gke.google_container_cluster.main"], cwd=stack_path, check=False)
    if untaint.returncode == 0:
        logger.info("Untainted GKE cluster (was tainted from previous failed apply)")

    old_cluster = f"{prefix}-gke-{env}-{region}"
    old_plan_vars = [
        f"-var=prefix={prefix}", f"-var=env={env}",
        f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
        f"-var=gke_cluster_name={old_cluster}",
        f"-var=gke_location={region}",
        f"-var=initial_node_count=1",
        f"-var=gke_deletion_protection=false",
        f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
    ]
    logger.step("GKE migration: disabling deletion_protection on existing regional cluster...")
    result = terra(["plan", "-out=tfplan_migration"] + old_plan_vars, cwd=stack_path, check=False)
    if result.returncode != 0:
        logger.warning("GKE migration plan failed; skipping (cluster may already be zonal or not exist)")
        return
    apply_stack_with_plan(stack_path, old_plan_vars, region, plan_file="tfplan_migration")
    logger.success("GKE deletion_protection disabled")


def run_deploy_kube(
    repo_root: str,
    env: str,
    region: str,
    prefix: str,
    gcp_proj: str,
    args,
    stats: "DeployStats | None" = None,
) -> bool:
    """Deploy kube stack (GKE + frontend). Returns True if plan succeeded."""
    stack_path = os.path.join(repo_root, "infra_terraform/live_deploy/gcp/kube")
    bucket = resolve_state_bucket(region)
    gke_location = get_gke_location(region)
    zone = gke_location if gke_location != region else None
    initial_node_count = get_initial_node_count(region)

    if args.apply and getattr(args, "gke_disable_deletion_protection", False) and zone:
        _run_gke_deletion_protection_migration(repo_root, env, region, prefix, gcp_proj, bucket)

    plan_vars = [
        f"-var=prefix={prefix}", f"-var=env={env}",
        f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
        f"-var=gke_cluster_name={gke_cluster(env, region, zone=zone)}",
        f"-var=gke_location={gke_location}",
        f"-var=initial_node_count={initial_node_count}",
        f"-var=gke_deletion_protection=false",
        f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
    ]

    def _apply():
        return run_deploy_stack(stack_path, plan_vars, region, env, args.apply)

    if stats:
        with stats.timed("Tofu apply", "kube"):
            return _apply()
    return _apply()
