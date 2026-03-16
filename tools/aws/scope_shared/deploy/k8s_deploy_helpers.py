"""
K8s deploy helpers for EKS.

Re-exports shared logic from tools.cloud_shared.k8s_deploy_helpers (provider="aws").
AWS-specific: wait_for_aws_load_balancer_controller_ready.
"""
import os
import subprocess
import time

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.k8s_deploy_helpers import (
    CRONJOB_PERIODIC,
    JOB_BOOTSTRAP,
    K8S_NAMESPACE,
    _emit_pending_unreachable_investigation,
    _env_with_region,
    _get_failed_scheduling_events,
    _get_node_summary,
    _run_kubeconfig,
    verify_api_db_connected,
    wait_for_dns_resolvable,
)

load_dotenv()

# AWS Load Balancer Controller (kube-system)
LB_CONTROLLER_NS = "kube-system"
LB_CONTROLLER_DEPLOY = "aws-load-balancer-controller"
LB_CONTROLLER_LABEL = "app.kubernetes.io/name=aws-load-balancer-controller"


def _get_lb_controller_pod_status(env_vars: dict) -> tuple[int, str]:
    """Return (ready_replicas, pod_status_summary) for aws-load-balancer-controller."""
    try:
        out = subprocess.check_output([
            "kubectl", "get", "deployment", LB_CONTROLLER_DEPLOY, "-n", LB_CONTROLLER_NS,
            "-o", "jsonpath={.status.readyReplicas}",
        ], text=True, timeout=15, env=env_vars)
        ready = int(out.strip()) if out.strip() else 0
    except (subprocess.CalledProcessError, ValueError):
        ready = 0
    try:
        pods_out = subprocess.check_output([
            "kubectl", "get", "pods", "-n", LB_CONTROLLER_NS, "-l", LB_CONTROLLER_LABEL,
            "-o", "wide",
        ], text=True, timeout=15, env=env_vars)
        return ready, (pods_out.strip() or "no pods")
    except Exception:
        return ready, ""


def _emit_lb_controller_diagnostics(env_vars: dict) -> None:
    """Log kubectl describe and logs for aws-load-balancer-controller pods."""
    from tools.cloud_shared.logging import logger
    try:
        desc = subprocess.check_output(
            ["kubectl", "describe", "pod", "-n", LB_CONTROLLER_NS, "-l", LB_CONTROLLER_LABEL],
            text=True, timeout=30, env=env_vars,
        )
        logger.error(f"[LB Controller] Pod describe:\n" + (desc[:2000] + "..." if len(desc) > 2000 else desc))
    except Exception as e:
        logger.warning(f"[LB Controller] Could not describe pods: {e}")
    try:
        logs = subprocess.check_output(
            ["kubectl", "logs", "-n", LB_CONTROLLER_NS, "-l", LB_CONTROLLER_LABEL, "--tail=50", "--prefix=True"],
            text=True, timeout=30, env=env_vars, stderr=subprocess.STDOUT,
        )
        logger.error(f"[LB Controller] Pod logs (tail 50):\n" + (logs[:1500] + "..." if len(logs) > 1500 else logs or "(empty)"))
    except Exception as e:
        logger.warning(f"[LB Controller] Could not get pod logs: {e}")


def wait_for_aws_load_balancer_controller_ready(
    env: str,
    timeout_seconds: int = 300,
    check_interval_seconds: int = 15,
    min_ready_replicas: int = 1,
    region: str | None = None,
) -> bool:
    """
    Wait for aws-load-balancer-controller deployment to have at least min_ready_replicas ready.
    Fail-fast: raises SystemExit if not ready within timeout, or if any pod is in CrashLoopBackOff.
    """
    from tools.cloud_shared.logging import logger

    _run_kubeconfig("aws", env, region or os.environ.get("CLOUD_REGION", ""))
    env_vars = _env_with_region(region)

    start = time.time()
    last_status_log = 0.0
    status_interval = 60
    pending_failfast_grace = 90
    while time.time() - start < timeout_seconds:
        ready, pod_summary = _get_lb_controller_pod_status(env_vars)
        elapsed = int(time.time() - start)
        bad_statuses = ("CrashLoopBackOff", "Error", "ImagePullBackOff", "ErrImagePull")
        if any(s in pod_summary for s in bad_statuses):
            found = [s for s in bad_statuses if s in pod_summary]
            logger.error(f"[LB Controller] Pods in {found} (fail-fast after {elapsed}s)")
            logger.error("[LB Controller] Pod status:\n" + pod_summary)
            _emit_lb_controller_diagnostics(env_vars)
            raise SystemExit(1)
        if ready >= min_ready_replicas:
            logger.success(f"[LB Controller] Deployment ready ({ready} replicas) in {elapsed}s")
            return True

        if ready == 0 and "Pending" in pod_summary and elapsed >= pending_failfast_grace:
            events = _get_failed_scheduling_events(LB_CONTROLLER_NS, env_vars)
            _, has_unreachable = _get_node_summary(env_vars)
            if events and ("untolerated taint" in events or "nodes are available" in events) and has_unreachable:
                logger.error(f"[LB Controller] Pods Pending: nodes unreachable/tainted (fail-fast after {elapsed}s)")
                logger.error("[LB Controller] Pod status:\n" + pod_summary)
                _emit_pending_unreachable_investigation(LB_CONTROLLER_NS, LB_CONTROLLER_DEPLOY, env_vars, "aws")
                _emit_lb_controller_diagnostics(env_vars)
                raise SystemExit(1)
            if events and "0/" in events and "nodes are available" in events:
                logger.error(f"[LB Controller] Pods Pending: no schedulable nodes (fail-fast after {elapsed}s)")
                logger.error("[LB Controller] Pod status:\n" + pod_summary)
                _emit_pending_unreachable_investigation(LB_CONTROLLER_NS, LB_CONTROLLER_DEPLOY, env_vars, "aws")
                _emit_lb_controller_diagnostics(env_vars)
                raise SystemExit(1)

        if time.time() - last_status_log >= status_interval:
            logger.info(f"[LB Controller] Waiting for pods to be ready... ({elapsed}s elapsed)")
            if pod_summary:
                for line in pod_summary.split("\n")[:5]:
                    logger.info(f"  {line}")
            last_status_log = time.time()
        time.sleep(check_interval_seconds)

    logger.error(f"[LB Controller] Deployment did not become ready within {timeout_seconds}s")
    logger.error("[LB Controller] Pod status:")
    _, pod_summary = _get_lb_controller_pod_status(env_vars)
    if pod_summary:
        logger.error(pod_summary)
    if "Pending" in (pod_summary or ""):
        events = _get_failed_scheduling_events(LB_CONTROLLER_NS, env_vars)
        _, has_unreachable = _get_node_summary(env_vars)
        if events and ("untolerated taint" in events or "0/" in events) and has_unreachable:
            _emit_pending_unreachable_investigation(LB_CONTROLLER_NS, LB_CONTROLLER_DEPLOY, env_vars, "aws")
    _emit_lb_controller_diagnostics(env_vars)
    raise SystemExit(1)


# Wrappers with AWS defaults for backward compatibility (region optional)
def check_k8s_bootstrap_job_succeeded(env: str, region: str | None = None) -> bool:
    from tools.cloud_shared.k8s_deploy_helpers import check_k8s_bootstrap_job_succeeded as _check
    return _check(env, region or os.environ.get("CLOUD_REGION", ""), "aws")


def wait_for_fru_api_ready(env: str, region: str | None = None, **kwargs) -> bool:
    from tools.cloud_shared.k8s_deploy_helpers import wait_for_fru_api_ready as _wait
    return _wait(env, region or os.environ.get("CLOUD_REGION", ""), provider="aws", **kwargs)


def k8s_rollout_restart_api(env: str, region: str | None = None) -> None:
    from tools.cloud_shared.k8s_deploy_helpers import k8s_rollout_restart_api as _restart
    _restart(env, region or os.environ.get("CLOUD_REGION", ""), provider="aws")


def cronjob_is_suspended(region: str) -> bool:
    from tools.cloud_shared.k8s_deploy_helpers import cronjob_is_suspended as _sus
    return _sus(region, provider="aws")


def cronjob_suspend_if_needed(region: str) -> bool:
    from tools.cloud_shared.k8s_deploy_helpers import cronjob_suspend_if_needed as _sus
    return _sus(region, provider="aws")


def cronjob_unsuspend_if_needed(region: str) -> bool:
    from tools.cloud_shared.k8s_deploy_helpers import cronjob_unsuspend_if_needed as _unsus
    return _unsus(region, provider="aws")
