"""
Helpers for idempotent bootstrap: skip if already succeeded.

Used by deploy.py (ECS) and kube_apply.py (K8s) to avoid re-running bootstrap
when a successful run already completed. K8s pre-destroy (kubectl delete) lives
in tools/aws/kube/kube_pre_destroy.py for symmetry with kube_apply.py.
"""
import json
import socket
import urllib.request
import os
import subprocess
from tools.cloud_shared.env import load_dotenv

load_dotenv()

# Log pattern for bootstrap success (from run_analytics.py)
BOOTSTRAP_SUCCESS_PATTERN = "fru bootstrap success"

# K8s Job/CronJob names and namespace (must match infra_terraform/modules/cloud_shared/k8s/)
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"
K8S_NAMESPACE = "fru-kube"


def check_ecs_bootstrap_succeeded(env: str, log_group: str | None = None) -> bool:
    """
    Check CloudWatch logs for ECS bootstrap success. Used to skip re-running.
    Returns True if 'fru bootstrap success' found in log_group streams.
    Log group: /fru/{env}/spark (Spark task logs).
    """
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(None)
    lg = log_group or os.getenv("CLOUDWATCH_LOG_GROUP") or f"/fru/{env}/spark"
    try:
        out = subprocess.check_output([
            "aws", "logs", "describe-log-streams",
            "--log-group-name", lg,
            "--order-by", "LastEventTime",
            "--descending",
            "--limit", "5",
            "--region", region,
        ], text=True, timeout=10, stderr=subprocess.DEVNULL)
        streams = json.loads(out).get("logStreams", [])
        for s in streams:
            stream_name = s["logStreamName"]
            events = subprocess.check_output([
                "aws", "logs", "get-log-events",
                "--log-group-name", lg,
                "--log-stream-name", stream_name,
                "--limit", "200",
                "--region", region,
            ], text=True, timeout=10, stderr=subprocess.DEVNULL)
            if BOOTSTRAP_SUCCESS_PATTERN in events.lower():
                return True
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        pass
    return False


def check_k8s_bootstrap_job_succeeded(env: str) -> bool:
    """
    Check if Job fru-analytics-bootstrap-kube exists and has status.succeeded >= 1.
    Returns True if already succeeded (skip re-run).
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


def wait_for_fru_api_ready(
    env: str,
    timeout_seconds: int = 600,
    check_interval_seconds: int = 15,
    min_ready_replicas: int = 1,
    region: str | None = None,
) -> bool:
    """
    Wait for fru-api deployment to have at least min_ready_replicas ready.
    Fail-fast: raises SystemExit if not ready within timeout.
    Used after kube bootstrap to ensure API pods are up before wiring CloudFront.
    See War Story 43.
    """
    import time
    from tools.cloud_shared.logging import logger

    subprocess.run(["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env], check=False)
    env_vars = {**os.environ}
    if region:
        env_vars["CLOUD_REGION"] = region

    start = time.time()
    last_log = 0.0
    while time.time() - start < timeout_seconds:
        try:
            out = subprocess.check_output([
                "kubectl", "get", "deployment", "fru-api", "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.readyReplicas}"
            ], text=True, timeout=15, env=env_vars)
            ready = int(out.strip()) if out.strip() else 0
            if ready >= min_ready_replicas:
                elapsed = int(time.time() - start)
                logger.success(f"[Kube] fru-api deployment ready ({ready} replicas) in {elapsed}s")
                return True
        except (subprocess.CalledProcessError, ValueError):
            pass

        elapsed = int(time.time() - start)
        if time.time() - last_log >= 30:
            logger.info(f"[Kube] Waiting for fru-api pods to be ready... ({elapsed}s elapsed)")
            last_log = time.time()
        time.sleep(check_interval_seconds)

    # Fail-fast: do not continue deploy with broken API
    logger.error(f"[Kube] fru-api deployment did not become ready within {timeout_seconds}s")
    logger.error("Check: kubectl get pods -n fru-kube -l app=fru-api && kubectl describe pod -n fru-kube -l app=fru-api")
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
            logger.error("  → Ensure PGPASSWORD in .env matches Aurora; run ensure_secrets; re-bootstrap.")
            logger.error("  → See README_WAR_STORIES.md ## 44")
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
