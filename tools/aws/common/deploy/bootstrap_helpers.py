"""
Helpers for idempotent bootstrap: skip if already succeeded.

Used by deploy.py (ECS) and kube_apply.py (K8s) to avoid re-running bootstrap
when a successful run already completed. Teardown removes scheduler + bootstrap
before destroying the stack.

K8s pre-destroy: We use kubectl (not Terraform kubernetes provider) because moving
Namespace/Deployment/Service/CronJob/Job into Terraform would require templating,
provider config, and secret wiring—cons outweighed pros. See README_WAR_STORIES ##40.
"""
import json
import socket
import urllib.request
import os
import subprocess
from typing import TYPE_CHECKING

from tools.cloud_shared.env import load_dotenv

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats

load_dotenv()

# Log pattern for bootstrap success (from run_analytics.py)
BOOTSTRAP_SUCCESS_PATTERN = "fru bootstrap success"

# K8s Job/CronJob names and namespace (must match infra-modules/cloud-shared/k8s/)
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"
K8S_NAMESPACE = "fru-kube"


def check_ecs_bootstrap_succeeded(env: str, log_group: str | None = None) -> bool:
    """
    Check CloudWatch logs for ECS bootstrap success. Used to skip re-running.
    Returns True if 'fru bootstrap success' found in log_group streams.
    Log group: /fru/{env}/spark (Spark task logs).
    """
    region = os.getenv("CLOUD_REGION", os.getenv("AWS_REGION", "us-east-1"))
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
        env_vars["AWS_REGION"] = region

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
    timeout_seconds: int = 120,
    check_interval_sec: int = 5,
    heartbeat_interval_sec: int = 30,
) -> bool:
    """
    Wait for a hostname to be DNS-resolvable. Used after kube deploy when the NLB
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
    logger.error("  → AWS NLB DNS typically propagates in 1-2 min. Retry deploy or check network.")
    raise SystemExit(1)


def verify_api_db_connected(base_url: str, timeout_seconds: int = 30, max_retries: int = 3) -> bool:
    """
    Verify /health returns database=connected. Fail-fast if disconnected.
    Used after kube deploy to catch Aurora vs db_password_plain mismatch (War Story 44).
    Call wait_for_dns_resolvable(lb_host) before this; DNS propagation is handled there.
    Retries a few times for transient HTTP/connection issues.
    """
    import time
    from tools.cloud_shared.logging import logger

    url = f"{base_url.rstrip('/')}/health"
    last_err = None
    retry_interval_sec = 20
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
                hint = " (NLB DNS may still be propagating; AWS typically takes 1-2 min)" if is_dns else ""
                logger.info(
                    f"[DB] /health not reachable (attempt {attempt + 1}/{max_retries}){hint}, "
                    f"retrying in {retry_interval_sec}s..."
                )
                time.sleep(retry_interval_sec)
    logger.error(f"[DB] Could not verify /health at {url}: {last_err}")
    if last_err and ("nodename" in str(last_err).lower() or "not known" in str(last_err).lower()):
        logger.error("  → DNS resolution failed. NLB hostname may need 1-2 min to propagate. Re-run deploy or try the URL manually.")
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
        env_vars["AWS_REGION"] = region
    result = subprocess.run(
        ["kubectl", "rollout", "restart", "deployment/fru-api", "-n", K8S_NAMESPACE],
        capture_output=True, text=True, timeout=60, env=env_vars,
    )
    if result.returncode == 0:
        logger.info("[Kube] Rollout restart triggered for fru-api (pods will pick up updated secrets)")
    else:
        # Deployment might not exist yet on first deploy; non-fatal
        logger.warning(f"[Kube] Rollout restart skipped or failed: {result.stderr or result.stdout}")


def k8s_remove_bootstrap_and_scheduler(
    env: str,
    region: str | None = None,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Pre-destroy: scale deployment to 0, delete LoadBalancer service, CronJob, Job,
    namespace; wait for termination.

    Why needed: EKS cluster deletion is blocked by LoadBalancer (holds ENIs), running
    pods, and workloads. AWS rejects delete until these are gone.

    Why not Terraform: These K8s resources are applied via kubectl (kube_apply.py),
    not in Terraform. We could use Terraform kubernetes provider, but chose kubectl
    for simplicity (templating, provider config, secrets add complexity). See WAR ##40.
    """
    import time

    from tools.cloud_shared.logging import logger

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Try to configure kubectl; if cluster is gone, warn and skip kubectl steps
    result = subprocess.run(
        ["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or "") + (result.stdout or "")
        if "ResourceNotFoundException" in err or "No cluster found" in err.lower():
            cluster_name = os.getenv("EKS_CLUSTER_NAME") or f"{os.getenv('FRU_PREFIX', 'fru')}-{env}-eks"
            logger.warning(
                f"EKS cluster not found (name={cluster_name}, region={os.getenv('CLOUD_REGION', os.getenv('AWS_REGION', 'us-east-1'))}), "
                "likely already removed. Skipping pre-destroy kube cleanup."
            )
            return

    _quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}

    # 1. Scale deployment to 0 (faster pod termination)
    def _scale():
        subprocess.run(
            ["kubectl", "scale", "deployment", "fru-api", "--replicas=0", "-n", K8S_NAMESPACE],
            check=False, **_quiet
        )
    _timed("Deployment (scale to 0)", f"fru-api (ns={K8S_NAMESPACE})", _scale)

    # 2. Delete LoadBalancer service first (releases NLB/ENIs; avoids DependencyViolation)
    def _del_svc():
        subprocess.run(
            ["kubectl", "delete", "svc", "fru-api-svc", "--ignore-not-found", "-n", K8S_NAMESPACE],
            check=False, **_quiet
        )
    _timed("LoadBalancer service", f"fru-api-svc (ns={K8S_NAMESPACE})", _del_svc)

    # 3. Delete CronJob and Job
    def _del_cronjob():
        subprocess.run(
            ["kubectl", "delete", "cronjob", CRONJOB_PERIODIC, "--ignore-not-found", "-n", K8S_NAMESPACE],
            check=False, **_quiet
        )
    _timed("CronJob", CRONJOB_PERIODIC, _del_cronjob)

    def _del_job():
        subprocess.run(
            ["kubectl", "delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE],
            check=False, **_quiet
        )
    _timed("Job", JOB_BOOTSTRAP, _del_job)

    # 4. Delete namespace (cascades to any remaining resources)
    def _del_ns():
        subprocess.run(
            ["kubectl", "delete", "namespace", K8S_NAMESPACE, "--ignore-not-found"],
            check=False, **_quiet
        )
    _timed("Namespace (delete)", K8S_NAMESPACE, _del_ns)

    # 5. Wait for namespace to fully terminate (LoadBalancer release can take 1–2 min)
    def _wait_ns():
        for attempt in range(24):  # Up to 2 min
            out = subprocess.run(
                ["kubectl", "get", "namespace", K8S_NAMESPACE],
                capture_output=True, text=True, check=False,
            )
            if out.returncode != 0 or "NotFound" in (out.stderr or ""):
                break
            if attempt > 0 and attempt % 4 == 0:
                logger.info(f"Waiting for namespace {K8S_NAMESPACE} to terminate... ({attempt * 5}s)")
            time.sleep(5)
    _timed("Namespace (wait terminate)", K8S_NAMESPACE, _wait_ns)

    logger.info("Pre-destroy: removed kube deployments, service, CronJob, Job, and namespace.")
