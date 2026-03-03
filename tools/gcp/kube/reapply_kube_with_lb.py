#!/usr/bin/env python3
"""
Re-apply kube stack with GKE LoadBalancer hostname for Cloud CDN API origin.

Use when deploy finished with "LoadBalancer hostname not available" (GKE LB can take 5–10 min).
Same pattern as AWS: first apply without LB, kube_apply, poll for LB, second apply with hostname.
Reference: war_stories/WAR_STORIES_CLOUD_SHARED.md §25.

Usage:
  PYTHONPATH=. python tools/gcp/kube/reapply_kube_with_lb.py --env dev --region us-central1
"""
import argparse
import os
import subprocess
import sys
import time

from tools.cloud_shared.logging import logger
from tools.gcp.provider_config_handler import get_gke_location, get_initial_node_count
from tools.gcp.scope_shared.core.backend import resolve_state_bucket
from tools.gcp.scope_shared.core.resource_names import gke_cluster
from tools.gcp.scope_shared.deploy.deploy_common import apply_stack

K8S_NAMESPACE = "fru-kube"


def _try_get_lb_hostname_or_ip(env: str, region: str) -> str:
    """GKE LoadBalancer hostname or IP. Prefer hostname; Cloud CDN supports both via INTERNET_FQDN_PORT / INTERNET_IP_PORT."""
    try:
        hostname = subprocess.check_output(
            ["kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
             "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"],
            text=True,
            env={**os.environ, "CLOUD_REGION": region},
            timeout=10,
        )
        if (hostname or "").strip():
            return (hostname or "").strip()
        ip = subprocess.check_output(
            ["kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
             "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"],
            text=True,
            env={**os.environ, "CLOUD_REGION": region},
            timeout=10,
        )
        return (ip or "").strip()
    except Exception:
        return ""


def _poll_lb_hostname_or_ip(env: str, region: str, max_attempts: int = 60, interval_sec: int = 20) -> str:
    """Poll kubectl for LB hostname or IP. GKE LB can take 5–20 min."""
    logger.info(
        "Polling for GKE LoadBalancer hostname or IP (kubectl get svc fru-api-svc); "
        "up to %d attempts, %ds apart (~%d min total)",
        max_attempts, interval_sec, max_attempts * interval_sec // 60,
    )
    for attempt in range(max_attempts):
        host_or_ip = _try_get_lb_hostname_or_ip(env, region)
        if host_or_ip:
            logger.info("LoadBalancer ready: %s (after %d/%d attempts)", host_or_ip, attempt + 1, max_attempts)
            return host_or_ip
        if attempt < max_attempts - 1:
            logger.info("Waiting for LoadBalancer (attempt %d/%d, next check in %ds)...", attempt + 1, max_attempts, interval_sec)
            time.sleep(interval_sec)
    logger.warning(
        "LoadBalancer hostname/IP not available after %d attempts (~%d min). "
        "GKE may still be provisioning; try again later.",
        max_attempts, max_attempts * interval_sec // 60,
    )
    return ""


def main():
    ap = argparse.ArgumentParser(description="Re-apply kube stack with GKE LB hostname for Cloud CDN")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=os.getenv("CLOUD_REGION", "us-central1"))
    args = ap.parse_args()

    region = args.region
    env = args.env
    os.environ["CLOUD_REGION"] = region
    os.environ.setdefault("FRU_ENV", env)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    prefix = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    gcp_proj = os.getenv("GCP_PROJECT_ID", "")
    if not gcp_proj:
        logger.error("GCP_PROJECT_ID required")
        sys.exit(1)

    logger.step("Ensuring GKE kubeconfig...")
    subprocess.run(
        [sys.executable, "tools/gcp/kube/gke_kubeconfig.py", "--env", env, "--region", region],
        cwd=repo_root,
        check=True,
        env={**os.environ, "CLOUD_REGION": region},
    )

    logger.step("Polling for LoadBalancer hostname or IP...")
    hostname = _poll_lb_hostname_or_ip(env, region)
    if not hostname:
        logger.error(
            "LoadBalancer hostname/IP still not available. Cloud CDN cannot wire API origin. "
            "Try again in a few minutes when GKE has finished provisioning the external IP."
        )
        sys.exit(1)

    logger.success(f"LoadBalancer hostname: {hostname}")

    bucket = resolve_state_bucket(region)
    gke_location = get_gke_location(region)
    zone = gke_location if gke_location != region else None

    plan_vars = [
        f"-var=prefix={prefix}", f"-var=env={env}",
        f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
        f"-var=gke_cluster_name={gke_cluster(env, region, zone=zone)}",
        f"-var=gke_location={gke_location}",
        f"-var=initial_node_count={get_initial_node_count(region)}",
        f"-var=gke_deletion_protection=false",
        f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
        f"-var=ingress_hostname={hostname}",
    ]

    stack_path = os.path.join(repo_root, "infra_terraform/live_deploy/gcp/kube")
    logger.step("Re-applying kube stack with LoadBalancer hostname...")
    apply_stack(
        stack_path, plan_vars, region,
        target_first="module.frontend.google_compute_backend_service.api_internet[0]",
    )
    logger.success("Cloud CDN API origin wired to GKE LoadBalancer")


if __name__ == "__main__":
    main()
