"""
Shared kube pre-destroy: scale deployment, delete service, CronJob, Job, namespace.

Used by AWS (after eks_kubeconfig), GCP (after gke_kubeconfig), and local (current context).
Keeps kube teardown order and resource names DRY across providers.
"""
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats

K8S_NAMESPACE = "fru-kube"
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"


def run_k8s_cleanup(
    namespace: str = K8S_NAMESPACE,
    job_bootstrap: str = JOB_BOOTSTRAP,
    cronjob_periodic: str = CRONJOB_PERIODIC,
    stats: "TeardownStats | None" = None,
    timeout_sec: int = 60,
) -> None:
    """
    Run kubectl cleanup: scale deployment to 0, delete svc, cronjob, job, namespace.
    Assumes kubectl context is already set (e.g. by provider-specific kubeconfig).
    """
    from tools.cloud_shared.logging import logger

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    _quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}

    def _run(cmd: list[str]):
        logger.info(f"Pre-destroy kube: running `{' '.join(cmd)}`")
        try:
            subprocess.run(cmd, check=False, timeout=timeout_sec, **_quiet)
        except subprocess.TimeoutExpired:
            logger.warning(f"Pre-destroy kube: `{' '.join(cmd)}` timed out after {timeout_sec}s")

    _timed("Deployment (scale to 0)", "fru-api", lambda: _run(["kubectl", "scale", "deployment", "fru-api", "--replicas=0", "-n", namespace]))
    _timed("Service", "fru-api-svc", lambda: _run(["kubectl", "delete", "svc", "fru-api-svc", "--ignore-not-found", "-n", namespace]))
    _timed("CronJob", cronjob_periodic, lambda: _run(["kubectl", "delete", "cronjob", cronjob_periodic, "--ignore-not-found", "-n", namespace]))
    _timed("Job", job_bootstrap, lambda: _run(["kubectl", "delete", "job", job_bootstrap, "--ignore-not-found", "-n", namespace]))
    _timed("Namespace", namespace, lambda: _run(["kubectl", "delete", "namespace", namespace, "--ignore-not-found"]))

    logger.success("Pre-destroy kube: deployment, service, CronJob, Job, namespace removed.")
