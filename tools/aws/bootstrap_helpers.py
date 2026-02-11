"""
Helpers for idempotent bootstrap: skip if already succeeded.

Used by deploy.py (ECS) and kube_apply.py (K8s) to avoid re-running bootstrap
when a successful run already completed. Teardown removes scheduler + bootstrap
before destroying the stack.
"""
import json
import os
import subprocess
from tools._env import load_dotenv

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
    Log group: /fru/{env}/ecs-api (API container logs from ecs_alb).
    """
    region = os.getenv("AWS_REGION", "us-east-1")
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


def k8s_remove_bootstrap_and_scheduler(env: str) -> None:
    """
    Remove bootstrap Job and periodic CronJob before teardown.
    Ensures scheduler is stopped and bootstrap job is cleaned up.
    """
    subprocess.run(["python", "tools/aws/eks_kubeconfig.py", "--env", env], check=False)
    subprocess.run(["kubectl", "delete", "cronjob", CRONJOB_PERIODIC, "--ignore-not-found", "-n", K8S_NAMESPACE], check=False)
    subprocess.run(["kubectl", "delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE], check=False)
    subprocess.run(["kubectl", "delete", "namespace", K8S_NAMESPACE, "--ignore-not-found"], check=False)
