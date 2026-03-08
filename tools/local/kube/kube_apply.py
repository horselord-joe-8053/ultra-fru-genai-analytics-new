"""
Apply Kubernetes manifests (bootstrap + schedule) to Docker Desktop Kubernetes.

Uses the same templates as AWS/GCP but with local images and config.
Requires: Docker Desktop with Kubernetes enabled, kubectl.

Examples:
  python tools/local/kube/kube_apply.py --phase bootstrap
  python tools/local/kube/kube_apply.py --phase schedule
"""
import argparse
import base64
import os
import subprocess
import sys

from tools.cloud_shared.analytics_schedule import (
    get_required_analytics_scheduler_interval_seconds,
    seconds_to_cron,
)
from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.k8s_j2_render import render

load_dotenv()

K8S_NAMESPACE = "fru-kube"
JOB_BOOTSTRAP = "fru-analytics-bootstrap-kube"


def _kubectl(args: list, input_text: str | None = None) -> None:
    cmd = ["kubectl"] + args
    print("+", " ".join(cmd[: min(10, len(cmd))]), "..." if len(cmd) > 10 else "")
    r = subprocess.run(cmd, input=input_text, text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout or "", file=sys.stderr)
        raise SystemExit(r.returncode)


def _ensure_local_k8s_context() -> None:
    """Ensure kubectl context is Docker Desktop (or compatible local cluster)."""
    out = subprocess.run(
        ["kubectl", "config", "current-context"],
        capture_output=True,
        text=True,
    )
    ctx = (out.stdout or "").strip()
    if not ctx:
        print("Error: No kubectl context. Enable Kubernetes in Docker Desktop.", file=sys.stderr)
        raise SystemExit(1)
    if "docker" not in ctx.lower() and "kind" not in ctx.lower() and "minikube" not in ctx.lower():
        print(f"Warning: Context '{ctx}' may not be local. Expected docker-desktop, kind-*, or minikube.")


def _check_bootstrap_succeeded() -> bool:
    try:
        out = subprocess.check_output(
            [
                "kubectl", "get", "job", JOB_BOOTSTRAP, "-n", K8S_NAMESPACE,
                "-o", "jsonpath={.status.succeeded}",
            ],
            text=True,
            timeout=10,
        )
        return out.strip() and int(out.strip()) >= 1
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["bootstrap", "schedule"], required=True)
    ap.add_argument("--spark-image", default="fru-spark:local", help="Spark image (default: fru-spark:local)")
    ap.add_argument("--app-image", default="fru-api:local", help="API image (default: fru-api:local)")
    ap.add_argument("--force", action="store_true", help="Force bootstrap even if already succeeded")
    args = ap.parse_args()

    _ensure_local_k8s_context()

    # Local: postgres on host via docker compose; k8s pods use host.docker.internal
    pg_host = os.environ.get("PGHOST", "localhost")
    if pg_host == "localhost" or pg_host == "127.0.0.1":
        pg_host = "host.docker.internal"
    pg_port = os.environ.get("PGPORT", "5432")
    pg_database = os.environ.get("PGDATABASE", "fru_db")
    pg_user = os.environ.get("PGUSER", "postgres")
    pg_password = os.environ.get("PGPASSWORD", "")
    if not pg_password:
        print("Error: PGPASSWORD must be set in .env", file=sys.stderr)
        raise SystemExit(1)

    delta_root = "file:///tmp/delta"
    delta_table_path = "file:///tmp/delta/fru_sales"

    _kubectl(
        ["apply", "-f", "-"],
        input_text=f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {K8S_NAMESPACE}\n",
    )

    if args.phase == "bootstrap":
        # Secrets from .env
        secret_b64 = base64.b64encode(pg_password.encode()).decode()
        _kubectl(
            ["apply", "-f", "-"],
            input_text=f"""apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
  PGPASSWORD: {secret_b64}
""",
        )

        openai_key = os.environ.get("OPENAI_API_KEY", "sk-placeholder")
        claude_key = os.environ.get("CLAUDE_API_KEY", openai_key)
        app_secret = {"OPENAI_API_KEY": openai_key, "CLAUDE_API_KEY": claude_key}
        app_b64 = {k: base64.b64encode(v.encode()).decode() for k, v in app_secret.items()}
        app_secret_yml = f"""apiVersion: v1
kind: Secret
metadata:
  name: app-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
  OPENAI_API_KEY: {app_b64['OPENAI_API_KEY']}
  CLAUDE_API_KEY: {app_b64['CLAUDE_API_KEY']}
"""
        _kubectl(["apply", "-f", "-"], input_text=app_secret_yml)

        if not args.force and _check_bootstrap_succeeded():
            print(f"[LOCAL KUBE] Skip: Job {JOB_BOOTSTRAP} already succeeded (use --force to re-run)")
        else:
            subs = {
                "cloud_provider": "local",
                "SPARK_IMAGE": args.spark_image,
                "DELTA_ROOT": delta_root,
                "DELTA_TABLE_PATH": delta_table_path,
                "PGHOST": pg_host,
                "PGPORT": pg_port,
                "PGDATABASE": pg_database,
                "PGUSER": pg_user,
                "CLOUD_REGION": os.environ.get("CLOUD_REGION", "local"),
            }
            txt = render("bootstrap-job", subs)
            _kubectl(["delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE])
            _kubectl(["apply", "-f", "-"], input_text=txt)

        # Deploy API
        interval_sec = get_required_analytics_scheduler_interval_seconds()
        api_subs = {
            "cloud_provider": "local",
            "APP_IMAGE": args.app_image,
            "CONTAINER_IMAGE_TAGS": "",
            "CONTAINER_TYPE": "local-kube",
            "DEPLOY_SCOPE": "kube",
            "CLOUD_PROVIDER": "local",
            "PGHOST": pg_host,
            "PGPORT": pg_port,
            "PGUSER": pg_user,
            "PGDATABASE": pg_database,
            "ALLOWED_ORIGINS": "*",
            "CLOUD_REGION": os.environ.get("CLOUD_REGION", "local"),
            "DELTA_TABLE_PATH": delta_table_path,
            "DELTA_LAKE_PACKAGE": os.environ.get("DELTA_LAKE_PACKAGE", "io.delta:delta-spark_2.12:3.1.0"),
            "SPARK_HOME": "/opt/spark",
            "GCP_LLM_PROVIDER": os.environ.get("GCP_LLM_PROVIDER", "claude"),
            "ENABLE_ANALYTICS_SCHEDULER": os.environ.get("ENABLE_ANALYTICS_SCHEDULER", "true"),
            "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": str(interval_sec),
        }
        _kubectl(["apply", "-f", "-"], input_text=render("api-deployment", api_subs))
        # Local: NodePort for direct access (Docker Desktop LoadBalancer also works)
        svc_subs = {"cloud_provider": "local"}
        _kubectl(["apply", "-f", "-"], input_text=render("api-service", svc_subs))

    else:
        interval_sec = get_required_analytics_scheduler_interval_seconds()
        subs = {
            "cloud_provider": "local",
            "SPARK_IMAGE": args.spark_image,
            "DELTA_ROOT": delta_root,
            "DELTA_TABLE_PATH": delta_table_path,
            "SCHEDULE_CRON": seconds_to_cron(interval_sec),
            "PGHOST": pg_host,
            "PGPORT": pg_port,
            "PGDATABASE": pg_database,
            "PGUSER": pg_user,
            "CLOUD_REGION": os.environ.get("CLOUD_REGION", "local"),
        }
        txt = render("spark-cronjob", subs)
        _kubectl(["apply", "-f", "-"], input_text=txt)

    print("Local kube apply complete.")


if __name__ == "__main__":
    main()
