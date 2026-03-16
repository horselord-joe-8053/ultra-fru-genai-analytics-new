"""
Pre-destroy cleanup for EKS kube stack.

Mirrors kube_apply.py: kube_apply applies manifests (api-service, deployment, cronjob, job);
kube_pre_destroy removes them before tofu destroy. Both live under tools/aws/kube/ for symmetry.

Why kubectl (not Terraform): K8s resources are applied via kubectl (kube_apply.py), not in
Terraform state. Moving them into Terraform kubernetes provider would require templating,
provider config, and secret wiring—cons outweighed pros. See docs/war_stories/WAR_STORIES_CLOUD_SHARED.md ##20.
"""
import os
import subprocess
from typing import TYPE_CHECKING

from tools.aws.scope_shared.deploy.k8s_deploy_helpers import (
    CRONJOB_PERIODIC,
    JOB_BOOTSTRAP,
    K8S_NAMESPACE,
)

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats


def k8s_pre_destroy_cleanup(
    env: str,
    region: str | None = None,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Pre-destroy: scale deployment to 0, delete LoadBalancer service, CronJob, Job,
    namespace; wait for termination.

    EKS cluster deletion is blocked by LoadBalancer (holds ENIs), running pods, and
    workloads. AWS rejects delete until these are gone. This runs before tofu destroy
    of the kube stack.
    """
    import time

    from tools.cloud_shared.logging import logger
    from tools.aws.scope_shared.core.backend import resolve_region

    region = region or resolve_region(None)
    os.environ.setdefault("CLOUD_REGION", region)

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Try to configure kubectl; if cluster is gone, warn and skip kubectl steps
    logger.info("Pre-destroy kube: checking EKS cluster status...")
    try:
        result = subprocess.run(
            ["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except subprocess.TimeoutExpired:
        from tools.aws.scope_shared.core import resource_names
        cluster_name = resource_names.eks_cluster(env, region)
        logger.warning(
            f"Pre-destroy kube: eks_kubeconfig timed out (cluster {cluster_name} unreachable?). "
            "Skipping kubectl cleanup."
        )
        return

    if result.returncode != 0:
        err = (result.stderr or "") + (result.stdout or "")
        if "ResourceNotFoundException" in err or "No cluster found" in err.lower():
            from tools.aws.scope_shared.core import resource_names
            cluster_name = resource_names.eks_cluster(env, region)
            logger.warning(
                f"EKS cluster not found (name={cluster_name}, region={os.getenv('CLOUD_REGION', '').strip() or 'not set'}), "
                "likely already removed. Skipping pre-destroy kube cleanup."
            )
            return

    logger.info("Pre-destroy kube: cluster reachable, removing CronJob, Job, namespace...")
    _quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    _kubectl_timeout = 60

    def _run_kubectl(cmd: list[str]):
        logger.info(f"Pre-destroy kube: running `{' '.join(cmd)}`")
        try:
            subprocess.run(cmd, check=False, timeout=_kubectl_timeout, **_quiet)
        except subprocess.TimeoutExpired:
            logger.warning(f"Pre-destroy kube: `{' '.join(cmd)}` timed out after {_kubectl_timeout}s")

    # 1. Scale deployment to 0 (faster pod termination)
    def _scale():
        _run_kubectl(["kubectl", "scale", "deployment", "fru-api", "--replicas=0", "-n", K8S_NAMESPACE])
    _timed("Deployment (scale to 0)", f"fru-api (ns={K8S_NAMESPACE})", _scale)

    # 2. Delete LoadBalancer service first (releases LB/ENIs; avoids DependencyViolation)
    def _del_svc():
        _run_kubectl(["kubectl", "delete", "svc", "fru-api-svc", "--ignore-not-found", "-n", K8S_NAMESPACE])
    _timed("LoadBalancer service", f"fru-api-svc (ns={K8S_NAMESPACE})", _del_svc)

    # 3. Delete CronJob and Job
    def _del_cronjob():
        _run_kubectl(["kubectl", "delete", "cronjob", CRONJOB_PERIODIC, "--ignore-not-found", "-n", K8S_NAMESPACE])
    _timed("CronJob", CRONJOB_PERIODIC, _del_cronjob)

    def _del_job():
        _run_kubectl(["kubectl", "delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE])
    _timed("Job", JOB_BOOTSTRAP, _del_job)

    # 4. Delete namespace (cascades to any remaining resources)
    def _del_ns():
        _run_kubectl(["kubectl", "delete", "namespace", K8S_NAMESPACE, "--ignore-not-found"])
    _timed("Namespace (delete)", K8S_NAMESPACE, _del_ns)

    # 5. Wait for namespace to fully terminate (LoadBalancer release can take 2–5 min)
    def _wait_ns():
        cmd = f"kubectl get namespace {K8S_NAMESPACE}"
        logger.info(
            f"Pre-destroy kube: polling `{cmd}` until Terminating completes "
            "(AWS releasing LB/ENIs, up to 5 min)..."
        )
        for attempt in range(60):  # Up to 5 min
            out = subprocess.run(
                ["kubectl", "get", "namespace", K8S_NAMESPACE],
                capture_output=True, text=True, check=False, timeout=30,
            )
            if out.returncode != 0 or "NotFound" in (out.stderr or ""):
                break
            if attempt > 0 and attempt % 4 == 0:
                logger.info(
                    f"Pre-destroy kube: still waiting on `{cmd}` (namespace Terminating) ... ({attempt * 5}s)"
                )
            time.sleep(5)
    _timed("Namespace (wait terminate)", K8S_NAMESPACE, _wait_ns)

    logger.info("Pre-destroy: removed kube deployments, service, CronJob, Job, and namespace.")
