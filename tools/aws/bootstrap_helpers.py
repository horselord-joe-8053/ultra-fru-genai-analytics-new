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
import os
import subprocess
from typing import TYPE_CHECKING

from tools._env import load_dotenv

if TYPE_CHECKING:
    from tools.aws.teardown_stats import TeardownStats

load_dotenv()

# Log pattern for bootstrap success (from bootstrap.py / run_analytics_once)
BOOTSTRAP_SUCCESS_PATTERN = "fru bootstrap success"

# K8s Job/CronJob names and namespace (must match infra-modules/shared/k8s/)
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"
CRONJOB_PERIODIC = "fru-analytics-periodic-kube"
K8S_NAMESPACE = "fru-kube"


def check_ecs_bootstrap_succeeded(env: str, log_group: str | None = None) -> bool:
    """
    Check CloudWatch logs for ECS bootstrap success. Used to skip re-running.
    Returns True if 'fru bootstrap success' found in log_group streams.
    Log group: /fru/{env}/ecs-api (API container logs from ecs module).
    """
    region = os.getenv("CLOUD_REGION", os.getenv("AWS_REGION", "us-east-1"))
    lg = log_group or os.getenv("CLOUDWATCH_LOG_GROUP") or f"/fru/{env}/ecs-api"
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
    subprocess.run(["python", "tools/aws/eks_kubeconfig.py", "--env", env], check=False)
    try:
        out = subprocess.check_output([
            "kubectl", "get", "job", JOB_BOOTSTRAP, "-n", K8S_NAMESPACE,
            "-o", "jsonpath={.status.succeeded}"
        ], text=True, timeout=10)
        return out.strip() and int(out.strip()) >= 1
    except Exception:
        return False


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

    from tools import logger

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # Try to configure kubectl; if cluster is gone, warn and skip kubectl steps
    result = subprocess.run(
        ["python", "tools/aws/eks_kubeconfig.py", "--env", env],
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
