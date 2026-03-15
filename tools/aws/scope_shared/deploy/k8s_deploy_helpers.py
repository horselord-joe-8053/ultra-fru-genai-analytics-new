"""
K8s deploy helpers for EKS.

- cronjob_is_suspended, cronjob_suspend_if_needed, cronjob_unsuspend_if_needed: CronJob suspend state
  (real-time kubectl) and conditional suspend/unsuspend. Used during deploy to reduce memory spike.
- check_k8s_bootstrap_job_succeeded: Check if analytics bootstrap Job (first non-periodic run) already succeeded.
- wait_for_fru_api_ready, wait_for_aws_load_balancer_controller_ready: Wait for deployments with periodic pod
  status, CrashLoopBackOff fail-fast, and describe+logs on timeout. Also fail-fast when pods Pending due to
  node unreachable/taint (War Story 40-41): prints investigation + recovery playbook.
- wait_for_dns_resolvable, verify_api_db_connected, k8s_rollout_restart_api:
  General kube deploy helpers (DNS, DB health, secret refresh).
"""
import json
import socket
import urllib.request
import os
import subprocess
from tools.cloud_shared.env import load_dotenv

load_dotenv()

# K8s Job/CronJob names and namespace (must match infra_terraform/modules/cloud_shared/k8s/)
# Bootstrap = first (non-periodic) run of analytics; see kube_apply --phase bootstrap
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"
K8S_NAMESPACE = "fru-kube"


def _cronjob_env(region: str) -> dict:
    """Env for kubectl targeting the correct cluster (CLOUD_REGION used by eks_kubeconfig)."""
    return {**os.environ, "CLOUD_REGION": region}


def cronjob_is_suspended(region: str) -> bool:
    """
    Return True if the analytics CronJob is suspended (real-time state from cluster).
    Uses kubectl get -o jsonpath to read spec.suspend. Returns False on error or if unset.
    """
    try:
        out = subprocess.run(
            ["kubectl", "get", "cronjob", CRONJOB_PERIODIC, "-n", K8S_NAMESPACE,
             "-o", "jsonpath={.spec.suspend}"],
            capture_output=True, text=True, timeout=10,
            env=_cronjob_env(region),
        )
        return (out.stdout or "").strip().lower() == "true"
    except Exception:
        return False


def cronjob_suspend_if_needed(region: str) -> bool:
    """
    Suspend the analytics CronJob only if it is not already suspended.
    Returns True if a suspend patch was applied, False if already suspended or on error.
    """
    if cronjob_is_suspended(region):
        return False
    try:
        subprocess.run(
            ["kubectl", "patch", "cronjob", CRONJOB_PERIODIC, "-n", K8S_NAMESPACE,
             "-p", '{"spec":{"suspend":true}}'],
            capture_output=True, timeout=10,
            env=_cronjob_env(region),
        )
        return True
    except Exception:
        return False


def cronjob_unsuspend_if_needed(region: str) -> bool:
    """
    Unsuspend the analytics CronJob only if it is currently suspended.
    Returns True if an unsuspend patch was applied, False if already unsuspended or on error.
    Fixes case where CronJob was left suspended by a prior failed deploy (War Story 41).
    """
    if not cronjob_is_suspended(region):
        return False
    try:
        subprocess.run(
            ["kubectl", "patch", "cronjob", CRONJOB_PERIODIC, "-n", K8S_NAMESPACE,
             "-p", '{"spec":{"suspend":false}}'],
            capture_output=True, timeout=10,
            env=_cronjob_env(region),
        )
        return True
    except Exception:
        return False


def check_k8s_bootstrap_job_succeeded(env: str) -> bool:
    """
    Check if analytics bootstrap Job (fru-analytics-bootstrap-kube) exists and has status.succeeded >= 1.
    Returns True if already succeeded (skip re-run of first analytics job).
    """
    subprocess.run(["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env], check=False)
    try:
        out = subprocess.check_output([
            "kubectl", "get", "job", JOB_BOOTSTRAP, "-n", K8S_NAMESPACE,
            "-o", "jsonpath={.status.succeeded}"
        ], text=True, timeout=10)
        return out.strip() and int(out.strip()) >= 1
    except Exception:
        return False


def _get_pod_status(env_vars: dict) -> tuple[int, str]:
    """Return (ready_replicas, pod_status_summary)."""
    try:
        out = subprocess.check_output([
            "kubectl", "get", "deployment", "fru-api", "-n", K8S_NAMESPACE,
            "-o", "jsonpath={.status.readyReplicas}"
        ], text=True, timeout=15, env=env_vars)
        ready = int(out.strip()) if out.strip() else 0
    except (subprocess.CalledProcessError, ValueError):
        ready = 0
    try:
        pods_out = subprocess.check_output([
            "kubectl", "get", "pods", "-n", K8S_NAMESPACE, "-l", "app=fru-api",
            "-o", "wide"
        ], text=True, timeout=15, env=env_vars)
        return ready, (pods_out.strip() or "no pods")
    except Exception:
        return ready, ""


def _get_failed_scheduling_events(namespace: str, env_vars: dict) -> str:
    """Get recent FailedScheduling events in namespace. Returns concatenated messages."""
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "events", "-n", namespace,
             "--field-selector", "reason=FailedScheduling",
             "-o", "custom-columns=MESSAGE:.message", "--sort-by=.lastTimestamp"],
            text=True, timeout=10, env=env_vars,
        )
        lines = [l.strip() for l in out.strip().split("\n")[1:] if l.strip()]  # skip header
        return "\n".join(lines[:5]) if lines else ""  # dedupe by taking unique messages
    except Exception:
        return ""


def _get_node_summary(env_vars: dict) -> tuple[str, bool]:
    """Return (node_summary_text, has_unreachable_or_notready).
    has_unreachable_or_notready=True if any node is NotReady or has unreachable taint.
    """
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "nodes", "-o", "wide"],
            text=True, timeout=15, env=env_vars,
        )
        summary = out.strip() or "no nodes"
    except Exception:
        return "could not get nodes", True
    has_bad = "NotReady" in summary or "Unknown" in summary
    if not has_bad:
        try:
            taints_out = subprocess.check_output(
                ["kubectl", "get", "nodes", "-o", "jsonpath={range .items[*]}{.metadata.name}{\": \"}{.spec.taints[*].key}{\"\\n\"}{end}"],
                text=True, timeout=10, env=env_vars,
            )
            if "unreachable" in taints_out:
                has_bad = True
        except Exception:
            pass
    return summary, has_bad


def _get_node_conditions_and_events(env_vars: dict) -> tuple[str, str]:
    """Capture node conditions (when did it transition?) and recent cluster events.
    Returns (conditions_text, events_text). Run before terminating to diagnose root cause."""
    conditions = ""
    events = ""
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "nodes", "-o", "jsonpath={range .items[*]}{.metadata.name}{\"\\n\"}{end}"],
            text=True, timeout=10, env=env_vars,
        )
        names = [n.strip() for n in out.strip().split("\n") if n.strip()]
        for name in names[:3]:
            try:
                cond = subprocess.check_output(
                    ["kubectl", "describe", "node", name],
                    text=True, timeout=15, env=env_vars,
                )
                if "Conditions:" in cond:
                    idx = cond.find("Conditions:")
                    conditions += cond[idx : idx + 1200] + "\n---\n"
            except Exception:
                pass
    except Exception:
        pass
    try:
        ev = subprocess.check_output(
            ["kubectl", "get", "events", "-A", "--sort-by=.lastTimestamp"],
            text=True, timeout=15, env=env_vars,
        )
        lines = ev.strip().split("\n")
        events = "\n".join(lines[-25:]) if len(lines) > 25 else ev.strip()
    except Exception:
        pass
    return conditions, events


def _emit_pending_unreachable_investigation(
    namespace: str,
    deployment_name: str,
    env_vars: dict,
) -> None:
    """Emit full investigation when pods are Pending due to node unreachable/taint.
    Includes node status, conditions, events, and recovery playbook. See War Story 40-41.
    Captures root-cause diagnostics BEFORE suggesting terminate (EKS_NODE_KUBELET_CRONJOB.md §4).
    """
    from tools.cloud_shared.logging import logger

    logger.error("")
    logger.error("═══ INVESTIGATION: Pods Pending — Node Unreachable / Taint ═══")
    logger.error("")
    logger.error("Root cause: Node(s) are NotReady or have node.kubernetes.io/unreachable taint.")
    logger.error("Pods cannot schedule; scheduler reports '0/N nodes available' or 'untolerated taint(s)'.")
    logger.error("")
    logger.error("Common causes (see docs/war_stories/WAR_STORIES_CLOUD_SHARED.md §40-41):")
    logger.error("  • CronJob overload → kubelet stops → node NotReady (us-east-2 pattern)")
    logger.error("  • Deploy-trigger: helm upgrade + rollout restart + Spark → memory spike on t3.small")
    logger.error("  • Node instance terminated or unreachable")
    logger.error("  • Network issues between control plane and node")
    logger.error("")
    node_summary, _ = _get_node_summary(env_vars)
    logger.error("Node status:")
    for line in (node_summary or "no output").split("\n"):
        logger.error("  " + line)
    logger.error("")
    conditions, cluster_events = _get_node_conditions_and_events(env_vars)
    if conditions:
        logger.error("Node conditions (when did it transition? lastTransitionTime):")
        for line in (conditions[:1500] + "..." if len(conditions) > 1500 else conditions).split("\n"):
            logger.error("  " + line)
        logger.error("")
    if cluster_events:
        logger.error("Recent cluster events (look for NodeNotReady, OOMKilled, Evicted):")
        for line in cluster_events.split("\n")[:15]:
            logger.error("  " + line)
        logger.error("")
    events = _get_failed_scheduling_events(namespace, env_vars)
    if events:
        logger.error("Scheduler events (FailedScheduling):")
        for line in events.split("\n"):
            logger.error("  " + line)
        logger.error("")
    logger.error("Diagnose root cause BEFORE terminating (EKS_NODE_KUBELET_CRONJOB.md §4):")
    logger.error("  aws ec2 get-console-output --instance-id <id> --region <region> --output text | tail -100")
    logger.error("  (look for OOM killer, kubelet errors)")
    logger.error("")
    logger.error("Recovery playbook (docs/learned/cloud_shared/EKS_NODE_KUBELET_CRONJOB.md):")
    logger.error("  1. Suspend CronJob: kubectl patch cronjob fru-analytics-periodic-kube -n fru-kube -p '{\"spec\":{\"suspend\":true}}'")
    logger.error("  2. Delete periodic Jobs: kubectl get jobs -n fru-kube -o name | grep periodic | xargs kubectl delete -n fru-kube")
    logger.error("     (or: kubectl delete jobs -n fru-kube --all  # includes bootstrap; deploy will re-run it)")
    logger.error("  3. Force-delete stuck pods: kubectl delete pod <pod> -n fru-kube --force --grace-period=0")
    logger.error("  4. Terminate NotReady node: aws ec2 terminate-instances --instance-ids <id> --region <region>")
    logger.error("     (instance ID: kubectl get node -o jsonpath='{.items[0].spec.providerID}' | sed 's|.*/||')")
    logger.error("     (use AWS_PROFILE=admin if needed)")
    logger.error("  5. Wait ~3-4 min for ASG replacement, then re-run deploy")
    logger.error("  6. Re-enable CronJob: kubectl patch cronjob fru-analytics-periodic-kube -n fru-kube -p '{\"spec\":{\"suspend\":false}}'")
    logger.error("")
    logger.error("See WAR_STORIES_CLOUD_SHARED.md §40-41, EKS_NODE_KUBELET_CRONJOB.md")
    logger.error("")


def _emit_pod_diagnostics(env_vars: dict) -> None:
    """Log kubectl describe and logs for fru-api pods."""
    from tools.cloud_shared.logging import logger
    try:
        desc = subprocess.check_output(
            ["kubectl", "describe", "pod", "-n", K8S_NAMESPACE, "-l", "app=fru-api"],
            text=True, timeout=30, env=env_vars,
        )
        logger.error("[Kube] Pod describe:\n" + (desc[:2000] + "..." if len(desc) > 2000 else desc))
    except Exception as e:
        logger.warning(f"[Kube] Could not describe pods: {e}")
    try:
        logs = subprocess.check_output(
            ["kubectl", "logs", "-n", K8S_NAMESPACE, "-l", "app=fru-api", "--tail=30", "--prefix=True"],
            text=True, timeout=30, env=env_vars, stderr=subprocess.STDOUT,
        )
        logger.error("[Kube] Pod logs (tail 30):\n" + (logs[:1500] + "..." if len(logs) > 1500 else logs or "(empty)"))
    except Exception as e:
        logger.warning(f"[Kube] Could not get pod logs: {e}")


# AWS Load Balancer Controller (kube-system)
LB_CONTROLLER_NS = "kube-system"
LB_CONTROLLER_DEPLOY = "aws-load-balancer-controller"
LB_CONTROLLER_LABEL = "app.kubernetes.io/name=aws-load-balancer-controller"


def _get_lb_controller_pod_status(env_vars: dict) -> tuple[int, str]:
    """Return (ready_replicas, pod_status_summary) for aws-load-balancer-controller."""
    try:
        out = subprocess.check_output([
            "kubectl", "get", "deployment", LB_CONTROLLER_DEPLOY, "-n", LB_CONTROLLER_NS,
            "-o", "jsonpath={.status.readyReplicas}"
        ], text=True, timeout=15, env=env_vars)
        ready = int(out.strip()) if out.strip() else 0
    except (subprocess.CalledProcessError, ValueError):
        ready = 0
    try:
        pods_out = subprocess.check_output([
            "kubectl", "get", "pods", "-n", LB_CONTROLLER_NS, "-l", LB_CONTROLLER_LABEL,
            "-o", "wide"
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
    Periodic pod status every 60s; on timeout, emits kubectl describe + logs.
    """
    import time
    from tools.cloud_shared.logging import logger

    subprocess.run(["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env], check=False)
    env_vars = {**os.environ}
    if region:
        env_vars["CLOUD_REGION"] = region

    start = time.time()
    last_status_log = 0.0
    status_interval = 60
    pending_failfast_grace = 90
    while time.time() - start < timeout_seconds:
        ready, pod_summary = _get_lb_controller_pod_status(env_vars)
        elapsed = int(time.time() - start)
        if "CrashLoopBackOff" in pod_summary or "Error" in pod_summary:
            logger.error(f"[LB Controller] Pods in CrashLoopBackOff/Error (fail-fast after {elapsed}s)")
            logger.error("[LB Controller] Pod status:\n" + pod_summary)
            _emit_lb_controller_diagnostics(env_vars)
            raise SystemExit(1)
        if ready >= min_ready_replicas:
            logger.success(f"[LB Controller] Deployment ready ({ready} replicas) in {elapsed}s")
            return True

        # Fail-fast on node unreachable/taint (same as fru-api; War Story 40-41)
        if ready == 0 and "Pending" in pod_summary and elapsed >= pending_failfast_grace:
            events = _get_failed_scheduling_events(LB_CONTROLLER_NS, env_vars)
            _, has_unreachable = _get_node_summary(env_vars)
            if events and ("untolerated taint" in events or "nodes are available" in events) and has_unreachable:
                logger.error(f"[LB Controller] Pods Pending: nodes unreachable/tainted (fail-fast after {elapsed}s)")
                logger.error("[LB Controller] Pod status:\n" + pod_summary)
                _emit_pending_unreachable_investigation(LB_CONTROLLER_NS, LB_CONTROLLER_DEPLOY, env_vars)
                _emit_lb_controller_diagnostics(env_vars)
                raise SystemExit(1)
            if events and "0/" in events and "nodes are available" in events:
                logger.error(f"[LB Controller] Pods Pending: no schedulable nodes (fail-fast after {elapsed}s)")
                logger.error("[LB Controller] Pod status:\n" + pod_summary)
                _emit_pending_unreachable_investigation(LB_CONTROLLER_NS, LB_CONTROLLER_DEPLOY, env_vars)
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
            _emit_pending_unreachable_investigation(LB_CONTROLLER_NS, LB_CONTROLLER_DEPLOY, env_vars)
    _emit_lb_controller_diagnostics(env_vars)
    raise SystemExit(1)


def wait_for_fru_api_ready(
    env: str,
    timeout_seconds: int = 600,
    check_interval_seconds: int = 15,
    min_ready_replicas: int = 1,
    region: str | None = None,
) -> bool:
    """
    Wait for fru-api deployment to have at least min_ready_replicas ready.
    Fail-fast: raises SystemExit if not ready within timeout, or if any pod is in CrashLoopBackOff.
    Used after kube deploy to ensure API pods are up before wiring CloudFront.
    See War Story 43.
    """
    import time
    from tools.cloud_shared.logging import logger

    subprocess.run(["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env], check=False)
    env_vars = {**os.environ}
    if region:
        env_vars["CLOUD_REGION"] = region

    start = time.time()
    last_status_log = 0.0
    status_interval = 60
    pending_failfast_grace = 90  # seconds before fail-fast on unreachable/taint
    while time.time() - start < timeout_seconds:
        ready, pod_summary = _get_pod_status(env_vars)
        elapsed = int(time.time() - start)
        if "CrashLoopBackOff" in pod_summary or "Error" in pod_summary:
            logger.error(f"[Kube] fru-api pods in CrashLoopBackOff/Error (fail-fast after {elapsed}s)")
            logger.error("[Kube] Pod status:\n" + pod_summary)
            _emit_pod_diagnostics(env_vars)
            raise SystemExit(1)
        if ready >= min_ready_replicas:
            logger.success(f"[Kube] fru-api deployment ready ({ready} replicas) in {elapsed}s")
            return True

        # Fail-fast on node unreachable/taint (War Story 40-41): pods Pending, 0 ready, scheduler says no nodes
        if ready == 0 and "Pending" in pod_summary and elapsed >= pending_failfast_grace:
            events = _get_failed_scheduling_events(K8S_NAMESPACE, env_vars)
            node_summary, has_unreachable = _get_node_summary(env_vars)
            if events and ("untolerated taint" in events or "nodes are available" in events):
                if has_unreachable:
                    logger.error(f"[Kube] fru-api pods Pending: nodes unreachable/tainted (fail-fast after {elapsed}s)")
                    logger.error("[Kube] Pod status:\n" + pod_summary)
                    _emit_pending_unreachable_investigation(K8S_NAMESPACE, "fru-api", env_vars)
                    _emit_pod_diagnostics(env_vars)
                    raise SystemExit(1)
                if "0/" in events and "nodes are available" in events:
                    # 0 nodes available (e.g. no nodes at all)
                    logger.error(f"[Kube] fru-api pods Pending: no schedulable nodes (fail-fast after {elapsed}s)")
                    logger.error("[Kube] Pod status:\n" + pod_summary)
                    _emit_pending_unreachable_investigation(K8S_NAMESPACE, "fru-api", env_vars)
                    _emit_pod_diagnostics(env_vars)
                    raise SystemExit(1)

        if time.time() - last_status_log >= status_interval:
            logger.info(f"[Kube] Waiting for fru-api pods to be ready... ({elapsed}s elapsed)")
            if pod_summary:
                for line in pod_summary.split("\n")[:5]:
                    logger.info(f"  {line}")
            last_status_log = time.time()
        time.sleep(check_interval_seconds)

    logger.error(f"[Kube] fru-api deployment did not become ready within {timeout_seconds}s")
    logger.error("[Kube] Pod status:")
    _, pod_summary = _get_pod_status(env_vars)
    if pod_summary:
        logger.error(pod_summary)
    # If Pending + unreachable, emit investigation (War Story 40-41)
    if "Pending" in (pod_summary or ""):
        events = _get_failed_scheduling_events(K8S_NAMESPACE, env_vars)
        _, has_unreachable = _get_node_summary(env_vars)
        if events and ("untolerated taint" in events or "0/" in events) and has_unreachable:
            _emit_pending_unreachable_investigation(K8S_NAMESPACE, "fru-api", env_vars)
    _emit_pod_diagnostics(env_vars)
    raise SystemExit(1)


def wait_for_dns_resolvable(
    hostname: str,
    timeout_seconds: int = 300,
    check_interval_sec: int = 5,
    heartbeat_interval_sec: int = 30,
) -> bool:
    """
    Wait for a hostname to be DNS-resolvable. Used after kube deploy when the LB
    hostname is assigned by K8s immediately, but AWS DNS can take 1-2 minutes to
    propagate. Retries with heartbeat until resolvable or timeout.
    """
    import time
    from tools.cloud_shared.logging import logger

    start = time.time()
    last_heartbeat = 0
    while time.time() - start < timeout_seconds:
        try:
            socket.getaddrinfo(hostname, 80)
            elapsed = int(time.time() - start)
            logger.success(f"[DNS] {hostname} resolvable in {elapsed}s")
            return True
        except (socket.gaierror, OSError):
            pass

        elapsed = int(time.time() - start)
        if elapsed - last_heartbeat >= heartbeat_interval_sec and elapsed > 0:
            logger.info(f"[DNS] Waiting for {hostname} to resolve... ({elapsed}s elapsed)")
            last_heartbeat = elapsed
        time.sleep(check_interval_sec)

    logger.error(f"[DNS] {hostname} did not become resolvable within {timeout_seconds}s")
    logger.error("  → AWS LB DNS typically propagates in 1-2 min. Retry deploy or check network.")
    raise SystemExit(1)


def verify_api_db_connected(base_url: str, timeout_seconds: int = 30, max_retries: int = 3) -> bool:
    """
    Verify /health returns database=connected. Fail-fast if disconnected.
    Used after kube deploy to catch Aurora vs db_password_plain mismatch (War Story 44).
    Call wait_for_dns_resolvable(lb_host) before this; DNS propagation is handled there.
    Retries for transient HTTP/connection issues. LB target health checks can take 2-5 min.
    """
    import time
    from tools.cloud_shared.logging import logger

    url = f"{base_url.rstrip('/')}/health"
    last_err = None
    retry_interval_sec = 30
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data = json.loads(resp.read().decode())
            db_status = data.get("database", "unknown")
            db_err = data.get("database_error", "")
            if db_status == "connected":
                logger.success("[DB] API database: connected")
                return True
            logger.error(f"[DB] API database: {db_status}")
            if db_err:
                logger.error(f"  Error: {db_err}")
            logger.error("  → Ensure PGPASSWORD in .env matches Aurora; run ensure_secrets; re-run analytics bootstrap.")
            logger.error("  → See docs/war_stories/WAR_STORIES_AWS.md ## 26")
            raise SystemExit(1)
        except SystemExit:
            raise
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_dns = "nodename" in err_str or "not known" in err_str or "name or service not known" in err_str
            if attempt < max_retries - 1:
                hint = " (LB DNS may still be propagating; AWS typically takes 1-2 min)" if is_dns else ""
                logger.info(
                    f"[DB] /health not reachable (attempt {attempt + 1}/{max_retries}){hint}, "
                    f"retrying in {retry_interval_sec}s..."
                )
                time.sleep(retry_interval_sec)
    logger.error(f"[DB] Could not verify /health at {url}: {last_err}")
    if last_err and ("nodename" in str(last_err).lower() or "not known" in str(last_err).lower()):
        logger.error("  → DNS resolution failed. LB hostname may need 1-2 min to propagate. Re-run deploy or try the URL manually.")
    raise SystemExit(1)


def k8s_rollout_restart_api(env: str, region: str | None = None) -> None:
    """
    Restart fru-api deployment so pods pick up updated db-credentials/app-credentials.
    K8s does not hot-reload secret changes; rollout restart forces new pods.
    See War Story 44.
    """
    from tools.cloud_shared.logging import logger

    subprocess.run(["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env], check=False)
    env_vars = {**os.environ}
    if region:
        env_vars["CLOUD_REGION"] = region
    result = subprocess.run(
        ["kubectl", "rollout", "restart", "deployment/fru-api", "-n", K8S_NAMESPACE],
        capture_output=True, text=True, timeout=60, env=env_vars,
    )
    if result.returncode == 0:
        logger.info("[Kube] Rollout restart triggered for fru-api (pods will pick up updated secrets)")
    else:
        # Deployment might not exist yet on first deploy; non-fatal
        logger.warning(f"[Kube] Rollout restart skipped or failed: {result.stderr or result.stdout}")
