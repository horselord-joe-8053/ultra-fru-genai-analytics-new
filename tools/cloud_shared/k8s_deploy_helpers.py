"""
Shared K8s deploy helpers for EKS and GKE.

Provider-agnostic logic: pod status, CrashLoopBackOff fail-fast, verify_api_db_connected, etc.
Callers pass ensure_kube_context (or provider) so kubectl targets the correct cluster.

Used by: tools/aws/scope_shared/deploy/k8s_deploy_helpers, tools/gcp/kube/deploy_kube.
"""
import json
import os
import socket
import subprocess
import sys
import urllib.request
from tools.cloud_shared.env import load_dotenv

load_dotenv()

# K8s names (must match infra_terraform/modules/cloud_shared/k8s/)
K8S_NAMESPACE = "fru-kube"
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"


def _run_kubeconfig(provider: str, env: str, region: str) -> None:
    """Run provider-specific kubeconfig script. Sets kubectl context."""
    if provider == "aws":
        subprocess.run(
            [sys.executable, "tools/aws/kube/eks_kubeconfig.py", "--env", env],
            check=False,
            env={**os.environ, "CLOUD_REGION": region},
        )
    elif provider == "gcp":
        subprocess.run(
            [sys.executable, "tools/gcp/kube/gke_kubeconfig.py", "--env", env, "--region", region],
            check=False,
            env={**os.environ, "CLOUD_REGION": region},
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _env_with_region(region: str | None) -> dict:
    env = {**os.environ}
    if region:
        env["CLOUD_REGION"] = region
    return env


def check_k8s_bootstrap_job_succeeded(
    env: str,
    region: str,
    provider: str = "aws",
) -> bool:
    """
    Check if Job fru-analytics-bootstrap-kube has status.succeeded >= 1.
    Runs provider kubeconfig, then kubectl get job.
    """
    _run_kubeconfig(provider, env, region)
    env_vars = _env_with_region(region)
    try:
        out = subprocess.check_output(
            [
                "kubectl", "get", "job", JOB_BOOTSTRAP, "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.succeeded}",
            ],
            text=True,
            timeout=10,
            env=env_vars,
        )
        return bool(out.strip() and int(out.strip()) >= 1)
    except Exception:
        return False


def _get_pod_status(env_vars: dict) -> tuple[int, str]:
    """Return (ready_replicas, pod_status_summary) for fru-api deployment."""
    try:
        out = subprocess.check_output([
            "kubectl", "get", "deployment", "fru-api", "-n", K8S_NAMESPACE,
            "-o", "jsonpath={.status.readyReplicas}",
        ], text=True, timeout=15, env=env_vars)
        ready = int(out.strip()) if out.strip() else 0
    except (subprocess.CalledProcessError, ValueError):
        ready = 0
    try:
        pods_out = subprocess.check_output([
            "kubectl", "get", "pods", "-n", K8S_NAMESPACE, "-l", "app=fru-api",
            "-o", "wide",
        ], text=True, timeout=15, env=env_vars)
        return ready, (pods_out.strip() or "no pods")
    except Exception:
        return ready, ""


def _get_failed_scheduling_events(namespace: str, env_vars: dict) -> str:
    """Get recent FailedScheduling events in namespace."""
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "events", "-n", namespace,
             "--field-selector", "reason=FailedScheduling",
             "-o", "custom-columns=MESSAGE:.message", "--sort-by=.lastTimestamp"],
            text=True, timeout=10, env=env_vars,
        )
        lines = [l.strip() for l in out.strip().split("\n")[1:] if l.strip()]
        return "\n".join(lines[:5]) if lines else ""
    except Exception:
        return ""


def _get_node_summary(env_vars: dict) -> tuple[str, bool]:
    """Return (node_summary_text, has_unreachable_or_notready)."""
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
    """Capture node conditions and recent cluster events."""
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
                    conditions += cond[idx: idx + 1200] + "\n---\n"
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
    provider: str = "aws",
) -> None:
    """Emit investigation when pods Pending due to node unreachable/taint. See War Story 40-41."""
    from tools.cloud_shared.logging import logger

    logger.error("")
    logger.error("═══ INVESTIGATION: Pods Pending — Node Unreachable / Taint ═══")
    logger.error("")
    logger.error("Root cause: Node(s) are NotReady or have node.kubernetes.io/unreachable taint.")
    logger.error("Pods cannot schedule; scheduler reports '0/N nodes available' or 'untolerated taint(s)'.")
    logger.error("")
    logger.error("Common causes (see docs/war_stories/WAR_STORIES_CLOUD_SHARED.md §40-41):")
    logger.error("  • CronJob overload → kubelet stops → node NotReady")
    logger.error("  • Deploy-trigger: rollout restart + Spark → memory spike")
    logger.error("  • Node instance terminated or unreachable")
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
    logger.error("Recovery playbook (docs/learned/cloud_shared/EKS_NODE_KUBELET_CRONJOB.md for AWS):")
    logger.error("  1. Suspend CronJob: kubectl patch cronjob fru-analytics-periodic-kube -n fru-kube -p '{\"spec\":{\"suspend\":true}}'")
    logger.error("  2. Delete periodic Jobs: kubectl get jobs -n fru-kube -o name | grep periodic | xargs kubectl delete -n fru-kube")
    logger.error("  3. Force-delete stuck pods: kubectl delete pod <pod> -n fru-kube --force --grace-period=0")
    if provider == "aws":
        logger.error("  4. Terminate NotReady node: aws ec2 terminate-instances --instance-ids <id> --region <region>")
        logger.error("     (instance ID: kubectl get node -o jsonpath='{.items[0].spec.providerID}' | sed 's|.*/||')")
    else:
        logger.error("  4. Delete/recreate NotReady node (GCP: gcloud compute instances delete or resize node pool)")
    logger.error("  5. Wait for replacement, then re-run deploy")
    logger.error("  6. Re-enable CronJob: kubectl patch cronjob fru-analytics-periodic-kube -n fru-kube -p '{\"spec\":{\"suspend\":false}}'")
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


def wait_for_fru_api_ready(
    env: str,
    region: str,
    provider: str = "aws",
    timeout_seconds: int = 600,
    check_interval_seconds: int = 15,
    min_ready_replicas: int = 1,
) -> bool:
    """
    Wait for fru-api deployment to have at least min_ready_replicas ready.
    Fail-fast: raises SystemExit if not ready within timeout, or if any pod is in CrashLoopBackOff.
    provider: "aws" or "gcp" — runs the corresponding kubeconfig before waiting.
    """
    import time
    from tools.cloud_shared.logging import logger

    _run_kubeconfig(provider, env, region)
    env_vars = _env_with_region(region)

    start = time.time()
    last_status_log = 0.0
    status_interval = 60
    pending_failfast_grace = 90
    while time.time() - start < timeout_seconds:
        ready, pod_summary = _get_pod_status(env_vars)
        elapsed = int(time.time() - start)
        # Fail-fast on pod startup failures (symptom detection)
        bad_statuses = ("CrashLoopBackOff", "Error", "ImagePullBackOff", "ErrImagePull")
        if any(s in pod_summary for s in bad_statuses):
            found = [s for s in bad_statuses if s in pod_summary]
            logger.error(f"[Kube] fru-api pods in {found} (fail-fast after {elapsed}s)")
            logger.error("[Kube] Pod status:\n" + pod_summary)
            _emit_pod_diagnostics(env_vars)
            raise SystemExit(1)
        if ready >= min_ready_replicas:
            logger.success(f"[Kube] fru-api deployment ready ({ready} replicas) in {elapsed}s")
            return True

        if ready == 0 and "Pending" in pod_summary and elapsed >= pending_failfast_grace:
            events = _get_failed_scheduling_events(K8S_NAMESPACE, env_vars)
            node_summary, has_unreachable = _get_node_summary(env_vars)
            if events and ("untolerated taint" in events or "nodes are available" in events):
                if has_unreachable:
                    logger.error(f"[Kube] fru-api pods Pending: nodes unreachable/tainted (fail-fast after {elapsed}s)")
                    logger.error("[Kube] Pod status:\n" + pod_summary)
                    _emit_pending_unreachable_investigation(K8S_NAMESPACE, "fru-api", env_vars, provider)
                    _emit_pod_diagnostics(env_vars)
                    raise SystemExit(1)
                if "0/" in events and "nodes are available" in events:
                    logger.error(f"[Kube] fru-api pods Pending: no schedulable nodes (fail-fast after {elapsed}s)")
                    logger.error("[Kube] Pod status:\n" + pod_summary)
                    _emit_pending_unreachable_investigation(K8S_NAMESPACE, "fru-api", env_vars, provider)
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
    if "Pending" in (pod_summary or ""):
        events = _get_failed_scheduling_events(K8S_NAMESPACE, env_vars)
        _, has_unreachable = _get_node_summary(env_vars)
        if events and ("untolerated taint" in events or "0/" in events) and has_unreachable:
            _emit_pending_unreachable_investigation(K8S_NAMESPACE, "fru-api", env_vars, provider)
    _emit_pod_diagnostics(env_vars)
    raise SystemExit(1)


def wait_for_dns_resolvable(
    hostname: str,
    timeout_seconds: int = 300,
    check_interval_sec: int = 5,
    heartbeat_interval_sec: int = 30,
) -> bool:
    """Wait for hostname to be DNS-resolvable. Used after kube deploy when LB DNS propagates."""
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
    raise SystemExit(1)


def _emit_verify_failure_diagnostics(
    env: str,
    region: str,
    provider: str,
) -> None:
    """Emit kubectl diagnostics when /health verification fails. Helps diagnose LB/backend issues."""
    from tools.cloud_shared.logging import logger

    _run_kubeconfig(provider, env, region)
    env_vars = _env_with_region(region)
    try:
        pods = subprocess.check_output(
            ["kubectl", "get", "pods", "-n", K8S_NAMESPACE, "-l", "app=fru-api", "-o", "wide"],
            text=True, timeout=15, env=env_vars,
        )
        logger.error("[Verify] fru-api pods:\n" + (pods.strip() or "(none)"))
    except Exception as e:
        logger.warning(f"[Verify] Could not get pods: {e}")
    try:
        ep = subprocess.check_output(
            ["kubectl", "get", "endpoints", "fru-api-svc", "-n", K8S_NAMESPACE, "-o", "wide"],
            text=True, timeout=10, env=env_vars,
        )
        logger.error("[Verify] fru-api-svc endpoints:\n" + (ep.strip() or "(none)"))
    except Exception as e:
        logger.warning(f"[Verify] Could not get endpoints: {e}")
    try:
        svc = subprocess.check_output(
            ["kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE],
            text=True, timeout=10, env=env_vars,
        )
        logger.error("[Verify] fru-api-svc:\n" + (svc.strip() or "(none)"))
    except Exception as e:
        logger.warning(f"[Verify] Could not get svc: {e}")


def verify_api_db_connected(
    base_url: str,
    timeout_seconds: int = 30,
    max_retries: int = 3,
    env: str | None = None,
    region: str | None = None,
    provider: str = "aws",
) -> bool:
    """
    Verify /health returns database=connected. Fail-fast if disconnected.
    Retries for transient HTTP/connection issues.
    On 502/connectivity failure: emits symptom-specific diagnostics (pods, endpoints, svc).
    """
    import time
    from urllib.error import HTTPError

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
            logger.error("  → Ensure secrets match DB; run ensure_secrets; re-run analytics bootstrap.")
            raise SystemExit(1)
        except SystemExit:
            raise
        except HTTPError as e:
            last_err = e
            if e.code == 502:
                logger.error(
                    f"[Verify] HTTP 502 at {url} (attempt {attempt + 1}/{max_retries}) — "
                    "Likely: LoadBalancer has no healthy backends (health checks failing)."
                )
                if env and region and attempt >= max_retries - 1:
                    logger.error("  → Check: pods not ready, wrong port, or LB health check path.")
                    _emit_verify_failure_diagnostics(env, region, provider)
                if attempt < max_retries - 1:
                    logger.info(f"  Retrying in {retry_interval_sec}s...")
                    time.sleep(retry_interval_sec)
                else:
                    raise SystemExit(1)
            else:
                logger.error(f"[Verify] HTTP {e.code} at {url}: {e}")
                raise SystemExit(1)
        except (OSError, urllib.error.URLError) as e:
            last_err = e
            err_str = str(e).lower()
            is_dns = "nodename" in err_str or "not known" in err_str or "name or service not known" in err_str
            is_conn = "connection refused" in err_str or "timed out" in err_str or "timeout" in err_str
            if is_conn and env and region and attempt >= max_retries - 1:
                logger.error(
                    f"[Verify] Connection failed at {url} — "
                    "Likely: LoadBalancer not ready, firewall, or backend not listening."
                )
                _emit_verify_failure_diagnostics(env, region, provider)
            if attempt < max_retries - 1:
                hint = " (LB DNS may still be propagating)" if is_dns else ""
                logger.info(f"[DB] /health not reachable (attempt {attempt + 1}/{max_retries}){hint}, retrying in {retry_interval_sec}s...")
                time.sleep(retry_interval_sec)
            else:
                logger.error(f"[DB] Could not verify /health at {url}: {last_err}")
                raise SystemExit(1)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_dns = "nodename" in err_str or "not known" in err_str or "name or service not known" in err_str
            if attempt < max_retries - 1:
                hint = " (LB DNS may still be propagating)" if is_dns else ""
                logger.info(f"[DB] /health not reachable (attempt {attempt + 1}/{max_retries}){hint}, retrying in {retry_interval_sec}s...")
                time.sleep(retry_interval_sec)
            else:
                logger.error(f"[DB] Could not verify /health at {url}: {last_err}")
                raise SystemExit(1)
    logger.error(f"[DB] Could not verify /health at {url}: {last_err}")
    raise SystemExit(1)


def verify_api_via_proxy(
    proxy_url: str,
    timeout_seconds: int = 30,
) -> bool:
    """
    Verify /health via the Cloud Run proxy URL (GCP kube only).
    Detects: Cloud Run → GKE LB connectivity failure.
    Call after verify_api_db_connected (direct LB) succeeds; if this fails, the proxy path is broken.
    """
    from tools.cloud_shared.logging import logger

    url = f"{proxy_url.rstrip('/')}/health"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode())
        if data.get("database") == "connected":
            logger.success("[Verify] API reachable via proxy (Cloud Run → GKE LB OK)")
            return True
        logger.warning(f"[Verify] Proxy returned /health but database={data.get('database', 'unknown')}")
        return False
    except Exception as e:
        logger.error(
            f"[Verify] Proxy /health failed at {url}: {e} — "
            "Likely: Cloud Run cannot reach GKE LB (firewall, LB not ready, or proxy misconfig)."
        )
        logger.error("  → Check: gcloud run services logs, GKE LB health, firewall rules.")
        raise SystemExit(1)


def k8s_rollout_restart_api(env: str, region: str, provider: str = "aws") -> None:
    """Restart fru-api deployment so pods pick up updated secrets."""
    from tools.cloud_shared.logging import logger

    _run_kubeconfig(provider, env, region)
    env_vars = _env_with_region(region)
    result = subprocess.run(
        ["kubectl", "rollout", "restart", "deployment/fru-api", "-n", K8S_NAMESPACE],
        capture_output=True, text=True, timeout=60, env=env_vars,
    )
    if result.returncode == 0:
        logger.info("[Kube] Rollout restart triggered for fru-api (pods will pick up updated secrets)")
    else:
        logger.warning(f"[Kube] Rollout restart skipped or failed: {result.stderr or result.stdout}")


def cronjob_is_suspended(region: str, provider: str = "aws", env: str | None = None) -> bool:
    """Return True if analytics CronJob is suspended."""
    _run_kubeconfig(provider, env or os.environ.get("FRU_ENV", "dev"), region)
    env_vars = _env_with_region(region)
    try:
        out = subprocess.run(
            ["kubectl", "get", "cronjob", CRONJOB_PERIODIC, "-n", K8S_NAMESPACE,
             "-o", "jsonpath={.spec.suspend}"],
            capture_output=True, text=True, timeout=10, env=env_vars,
        )
        return (out.stdout or "").strip().lower() == "true"
    except Exception:
        return False


def cronjob_suspend_if_needed(region: str, provider: str = "aws") -> bool:
    """Suspend CronJob only if not already suspended."""
    if cronjob_is_suspended(region, provider):
        return False
    _run_kubeconfig(provider, os.environ.get("FRU_ENV", "dev"), region)
    env_vars = _env_with_region(region)
    try:
        subprocess.run(
            ["kubectl", "patch", "cronjob", CRONJOB_PERIODIC, "-n", K8S_NAMESPACE,
             "-p", '{"spec":{"suspend":true}}'],
            capture_output=True, timeout=10, env=env_vars,
        )
        return True
    except Exception:
        return False


def cronjob_unsuspend_if_needed(region: str, provider: str = "aws") -> bool:
    """Unsuspend CronJob only if currently suspended."""
    if not cronjob_is_suspended(region, provider):
        return False
    _run_kubeconfig(provider, os.environ.get("FRU_ENV", "dev"), region)
    env_vars = _env_with_region(region)
    try:
        subprocess.run(
            ["kubectl", "patch", "cronjob", CRONJOB_PERIODIC, "-n", K8S_NAMESPACE,
             "-p", '{"spec":{"suspend":false}}'],
            capture_output=True, timeout=10, env=env_vars,
        )
        return True
    except Exception:
        return False
