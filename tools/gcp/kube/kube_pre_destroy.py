"""
Pre-destroy cleanup for GKE kube stack.

Mirrors kube_apply.py: kube_apply applies manifests (api-service, deployment, cronjob, job);
kube_pre_destroy removes them before tofu destroy. Reference: tools/aws/kube/kube_pre_destroy.py.

Why kubectl (not Terraform): K8s resources are applied via kubectl (kube_apply.py), not in
Terraform state. See war_stories/WAR_STORIES_CLOUD_SHARED.md ##20.
"""
import os
import subprocess
from typing import TYPE_CHECKING

K8S_NAMESPACE = "fru-kube"
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"

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

    GKE cluster deletion is blocked by LoadBalancer and running workloads.
    """
    import time

    from tools.cloud_shared.logging import logger
    from tools.gcp.scope_shared.core.backend import resolve_region

    region = region or resolve_region(None)
    os.environ.setdefault("CLOUD_REGION", region)

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    logger.info("Pre-destroy kube: checking GKE cluster status...")
    try:
        result = subprocess.run(
            ["python", "tools/gcp/kube/gke_kubeconfig.py", "--env", env, "--region", region],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env={**os.environ, "CLOUD_REGION": region},
        )
    except subprocess.TimeoutExpired:
        logger.warning("Pre-destroy kube: gke_kubeconfig timed out. Skipping kubectl cleanup.")
        return

    if result.returncode != 0:
        err = (result.stderr or "") + (result.stdout or "")
        if "not found" in err.lower() or "does not exist" in err.lower():
            logger.warning("GKE cluster not found, likely already removed. Skipping pre-destroy kube cleanup.")
            return

    logger.info("Pre-destroy kube: cluster reachable, removing CronJob, Job, namespace...")
    _quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    _kubectl_timeout = 60

    def _run_kubectl(cmd: list):
        logger.info(f"Pre-destroy kube: running `{' '.join(cmd)}`")
        try:
            subprocess.run(cmd, check=False, timeout=_kubectl_timeout, **_quiet)
        except subprocess.TimeoutExpired:
            logger.warning(f"Pre-destroy kube: `{' '.join(cmd)}` timed out after {_kubectl_timeout}s")

    def _scale():
        _run_kubectl(["kubectl", "scale", "deployment", "fru-api", "--replicas=0", "-n", K8S_NAMESPACE])
    _timed("Deployment (scale to 0)", f"fru-api (ns={K8S_NAMESPACE})", _scale)

    def _del_svc():
        _run_kubectl(["kubectl", "delete", "svc", "fru-api-svc", "--ignore-not-found", "-n", K8S_NAMESPACE])
    _timed("LoadBalancer service", f"fru-api-svc (ns={K8S_NAMESPACE})", _del_svc)

    def _del_cronjob():
        _run_kubectl(["kubectl", "delete", "cronjob", CRONJOB_PERIODIC, "--ignore-not-found", "-n", K8S_NAMESPACE])
    _timed("CronJob", CRONJOB_PERIODIC, _del_cronjob)

    def _del_job():
        _run_kubectl(["kubectl", "delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE])
    _timed("Job", JOB_BOOTSTRAP, _del_job)

    time.sleep(5)
    def _del_ns():
        _run_kubectl(["kubectl", "delete", "namespace", K8S_NAMESPACE, "--ignore-not-found"])
    _timed("Namespace", K8S_NAMESPACE, _del_ns)

    logger.success("Pre-destroy kube: CronJob, Job, namespace removed.")
