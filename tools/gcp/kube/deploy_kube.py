"""
Kube-specific deploy logic: GKE apply, kube_apply, LB wiring, frontend.

Called by deploy.py when scope is kube or all (after nonkube when scope=all).
Reference: tools/aws/kube/deploy_kube.py
"""
import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING

from tools.cloud_shared.logging import logger
from tools.gcp.provider_config_handler import get_gke_location, get_initial_node_count
from tools.gcp.scope_shared.core.backend import resolve_state_bucket
from tools.gcp.scope_shared.core.resource_names import gke_cluster
from tools.gcp.scope_shared.deploy.deploy_common import run_deploy_stack, apply_stack

if TYPE_CHECKING:
    from tools.cloud_shared.stats import DeployStats

K8S_NAMESPACE = "fru-kube"


def _try_get_lb_hostname_or_ip(env: str, region: str) -> str:
    """Try to get GKE LoadBalancer hostname or IP from kubectl. Prefer hostname; GKE often exposes IP only."""
    try:
        hostname = subprocess.check_output(
            [
                "kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}",
            ],
            text=True,
            env={**os.environ, "CLOUD_REGION": region},
            timeout=10,
        )
        if (hostname or "").strip():
            return (hostname or "").strip()
        ip = subprocess.check_output(
            [
                "kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}",
            ],
            text=True,
            env={**os.environ, "CLOUD_REGION": region},
            timeout=10,
        )
        return (ip or "").strip()
    except Exception:
        return ""


def _poll_lb_hostname_or_ip(env: str, region: str, max_attempts: int = 60, interval_sec: int = 20) -> str:
    """Poll kubectl for LB hostname or IP until available or max_attempts. GKE LB can take 5–20 min."""
    total_min = max_attempts * interval_sec // 60
    logger.info(
        f"Polling for GKE LoadBalancer hostname or IP (kubectl get svc fru-api-svc); "
        f"up to {max_attempts} attempts, {interval_sec}s apart (~{total_min} min total)"
    )
    for attempt in range(max_attempts):
        host_or_ip = _try_get_lb_hostname_or_ip(env, region)
        if host_or_ip:
            logger.info(f"LoadBalancer ready: {host_or_ip} (after {attempt + 1}/{max_attempts} attempts)")
            return host_or_ip
        if attempt < max_attempts - 1:
            logger.info(f"Waiting for LoadBalancer (attempt {attempt + 1}/{max_attempts}, next check in {interval_sec}s)...")
            time.sleep(interval_sec)
    return ""


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
    """Deploy kube stack: GKE apply, kube_apply, LB wiring, frontend. Returns True if plan succeeded."""
    stack_path = os.path.join(repo_root, "infra_terraform/live_deploy/gcp/kube")
    bucket = resolve_state_bucket(region)
    gke_location = get_gke_location(region)
    zone = gke_location if gke_location != region else None
    initial_node_count = get_initial_node_count(region)

    if args.apply and getattr(args, "gke_disable_deletion_protection", False) and zone:
        _run_gke_deletion_protection_migration(repo_root, env, region, prefix, gcp_proj, bucket)

    # Ensure kubectl targets GKE (not stale AWS EKS context) before any kubectl calls
    subprocess.run(
        [sys.executable, "tools/gcp/kube/gke_kubeconfig.py", "--env", env, "--region", region],
        cwd=repo_root,
        check=False,
        env={**os.environ, "CLOUD_REGION": region},
    )
    hostname_before = _try_get_lb_hostname_or_ip(env, region)
    if hostname_before:
        logger.info(f"[Kube] LB hostname known before apply: {hostname_before}; single apply (skip second)")

    plan_vars = [
        f"-var=prefix={prefix}", f"-var=env={env}",
        f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
        f"-var=gke_cluster_name={gke_cluster(env, region, zone=zone)}",
        f"-var=gke_location={gke_location}",
        f"-var=initial_node_count={initial_node_count}",
        f"-var=gke_deletion_protection=false",
        f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
    ]
    if hostname_before:
        plan_vars.append(f"-var=ingress_hostname={hostname_before}")

    # Target backend first when wiring API origin to fix FQDN<->IP migration destroy-order
    target_first = "module.frontend.google_compute_backend_service.api_internet[0]" if hostname_before else None

    def _apply():
        return run_deploy_stack(stack_path, plan_vars, region, env, args.apply, apply_target_first=target_first)

    if stats:
        with stats.timed("Tofu apply", "kube"):
            ok = _apply()
    else:
        ok = _apply()

    if not ok or not args.apply:
        return ok

    # kube_apply: bootstrap + schedule
    from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json

    nondurable = get_tofu_output_json(
        "infra_terraform/live_deploy/gcp/scope_shared/nondurable", env, region, "nondurable"
    )
    durable = get_tofu_output_json(
        "infra_terraform/live_deploy/gcp/scope_shared/durable", env, region, "durable"
    )
    delta_bucket = nondurable.get("delta_bucket_name", {}).get("value", "")
    pg_host = durable.get("cloud_sql_private_ip", {}).get("value", "localhost")
    spark_base = (nondurable.get("artifact_registry_spark_url", {}).get("value", "") or "").rstrip("/")
    app_base = (nondurable.get("artifact_registry_app_url", {}).get("value", "") or "").rstrip("/")
    if not spark_base or not app_base:
        raise ValueError(
            "artifact_registry_spark_url and artifact_registry_app_url required from nondurable. "
            "Run deploy without --skip-build first, or ensure shared nondurable stack is applied."
        )
    spark_img = f"{spark_base}:latest"
    app_img = f"{app_base}:latest"
    delta_table = f"gs://{delta_bucket}/delta/fru_sales"

    kube_apply_args = [
        sys.executable, "tools/gcp/kube/kube_apply.py", "--env", env, "--region", region, "--phase", "bootstrap",
        "--spark-image", spark_img, "--app-image", app_img,
        "--delta-bucket", delta_bucket,
        "--pg-host", pg_host or "localhost",
        "--delta-table-path", delta_table,
    ]
    if getattr(args, "force_refresh_data", False):
        kube_apply_args.append("--force")

    logger.step("K8s bootstrap (API + Job)...")
    if stats:
        with stats.timed("K8s bootstrap", "kube_apply bootstrap"):
            subprocess.run(kube_apply_args, check=True, cwd=repo_root, env={**os.environ, "CLOUD_REGION": region})
    else:
        subprocess.run(kube_apply_args, check=True, cwd=repo_root, env={**os.environ, "CLOUD_REGION": region})

    subprocess.run([
        sys.executable, "tools/gcp/kube/kube_apply.py", "--env", env, "--region", region, "--phase", "schedule",
        "--spark-image", spark_img, "--delta-bucket", delta_bucket,
        "--pg-host", pg_host or "localhost",
        "--delta-table-path", delta_table,
    ], check=True, cwd=repo_root, env={**os.environ, "CLOUD_REGION": region})
    logger.success("K8s bootstrap + schedule complete")

    # Poll for LB hostname, second apply if needed
    hostname_after = _poll_lb_hostname_or_ip(env, region)
    hostname_to_use = hostname_after or hostname_before
    need_second_apply = hostname_to_use and (
        not hostname_before or (hostname_after and hostname_after != hostname_before)
    )

    if need_second_apply:
        logger.step("Re-applying kube stack with LoadBalancer hostname for Cloud CDN API origin...")
        reapply_vars = plan_vars.copy()
        if f"-var=ingress_hostname={hostname_before}" in reapply_vars:
            reapply_vars = [v for v in reapply_vars if not v.startswith("-var=ingress_hostname=")]
        reapply_vars.append(f"-var=ingress_hostname={hostname_to_use}")
        apply_stack(
            stack_path, reapply_vars, region,
            target_first="module.frontend.google_compute_backend_service.api_internet[0]",
        )
        logger.success("Cloud CDN API origin wired to GKE LoadBalancer")
    elif hostname_to_use and hostname_to_use == hostname_before:
        logger.success("Cloud CDN API origin already wired (hostname unchanged)")
    elif not hostname_to_use:
        logger.warning(
            f"LoadBalancer hostname/IP not available after polling. Cloud CDN cannot route /api/* to GKE; "
            f"kube frontend will load but API calls may fail. Re-apply when LB is ready: "
            f"PYTHONPATH=. python tools/gcp/kube/reapply_kube_with_lb.py --env {env} --region {region}"
        )

    # Deploy frontend to GCS
    try:
        kube_out = get_tofu_output_json(
            "infra_terraform/live_deploy/gcp/kube", env, region, "kube"
        )
        frontend_bucket = kube_out.get("frontend_bucket_name", {}).get("value")
        if frontend_bucket:
            from tools.gcp.scope_shared.deploy.deploy_frontend import (
                deploy_frontend_to_gcs,
                invalidate_cloud_cdn,
            )
            deploy_frontend_to_gcs(frontend_bucket, env, scope="kube", project_id=gcp_proj)
            url_map = kube_out.get("url_map_name", {}).get("value")
            if url_map and gcp_proj:
                invalidate_cloud_cdn(url_map, gcp_proj)
        else:
            logger.warning("frontend_bucket_name not found; skipping kube frontend deploy")
    except Exception as e:
        logger.warning(f"Could not deploy kube frontend: {e}")

    return ok
