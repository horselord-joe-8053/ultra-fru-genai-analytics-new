"""
Apply Kubernetes manifests (bootstrap + schedule) to GKE.

GCP kube scope: API + CronJob on GKE. Uses gs://, GCP Secret Manager, GKE LoadBalancer.
Reference: tools/aws/kube/kube_apply.py (AWS EKS version).

Examples:
  python tools/gcp/kube/kube_apply.py --env dev --phase bootstrap
  python tools/gcp/kube/kube_apply.py --env dev --phase schedule
"""
import argparse
import base64
import os
import subprocess
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from tools.cloud_shared.analytics_schedule import (
    get_required_analytics_scheduler_interval_seconds,
    seconds_to_cron,
)
from tools.cloud_shared.env import load_dotenv, require
from tools.cloud_shared.k8s_deploy_helpers import JOB_BOOTSTRAP, K8S_NAMESPACE, check_k8s_bootstrap_job_succeeded
from tools.cloud_shared.k8s_j2_render import render
from tools.gcp.scope_shared.core.backend import resolve_region

load_dotenv()


def _kubectl(args: list, input_text: str | None = None) -> None:
    cmd = ["kubectl"] + args
    print("+", " ".join(cmd[: min(8, len(cmd))]), "..." if len(cmd) > 8 else "")
    subprocess.run(cmd, input=input_text, text=True, check=True)


def _fetch_gcp_secret(secret_id: str, project: str) -> str:
    """Fetch secret value from GCP Secret Manager."""
    if not secret_id:
        return ""
    timeout = int(os.getenv("GCP_SECRET_FETCH_TIMEOUT", "60"))
    out = subprocess.check_output(
        [
            "gcloud", "secrets", "versions", "access", "latest",
            "--secret", secret_id,
            "--project", project,
        ],
        text=True,
        timeout=timeout,
    )
    return (out or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    ap.add_argument("--phase", choices=["bootstrap", "schedule"], required=True)
    ap.add_argument("--spark-image", help="Full Spark image URI")
    ap.add_argument("--app-image", help="Full App image URI")
    ap.add_argument("--delta-bucket", help="GCS delta bucket")
    ap.add_argument("--pg-host", default="")
    ap.add_argument("--pg-port", default="5432")
    ap.add_argument("--pg-database", default="fru_db")
    ap.add_argument("--pg-user", default="postgres")
    ap.add_argument("--db-secret-id", default="", help="GCP Secret Manager secret ID for db_password")
    ap.add_argument("--openai-secret-id", default="", help="GCP Secret Manager secret ID for openai_api_key")
    ap.add_argument("--claude-secret-id", default="", help="GCP Secret Manager secret ID for claude_api_key")
    ap.add_argument("--google-secret-id", default="", help="GCP Secret Manager secret ID for google_ai_api_key")
    ap.add_argument("--delta-table-path", default="")
    ap.add_argument("--gcp-llm-provider", default=os.getenv("GCP_LLM_PROVIDER", "claude"))
    ap.add_argument("--claude-model", default=None, help="CLAUDE_MODEL from .env (required)")
    ap.add_argument("--google-model", default=None, help="GOOGLE_MODEL or GEMINI_MODEL from .env (required)")
    ap.add_argument("--force", action="store_true", help="Force bootstrap even if already succeeded")
    args = ap.parse_args()

    from core_app.backend.env_utils.cloud_shared.model_config import require_claude_model, require_google_model
    args.claude_model = args.claude_model or require_claude_model()
    args.google_model = args.google_model or require_google_model()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project:
        print("Error: GCP_PROJECT_ID must be set", file=__import__("sys").stderr)
        raise SystemExit(1)

    from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json

    # Ensure kubeconfig
    subprocess.run(
        ["python", "tools/gcp/kube/gke_kubeconfig.py", "--env", args.env, "--region", region],
        check=True,
        env={**os.environ, "CLOUD_REGION": region},
    )

    nondurable = get_tofu_output_json(
        "infra_terraform/live_deploy/gcp/scope_shared/nondurable", args.env, region, "nondurable"
    )
    durable = get_tofu_output_json(
        "infra_terraform/live_deploy/gcp/scope_shared/durable", args.env, region, "durable"
    )
    kube_out = get_tofu_output_json(
        "infra_terraform/live_deploy/gcp/kube", args.env, region, "kube"
    )

    delta_bucket = args.delta_bucket or nondurable.get("delta_bucket_name", {}).get("value", "")
    if not delta_bucket:
        raise SystemExit("delta_bucket not in nondurable outputs")
    delta_root = f"gs://{delta_bucket}/delta"
    delta_table_path = args.delta_table_path or f"gs://{delta_bucket}/delta/fru_sales"

    spark_base = nondurable.get("artifact_registry_spark_url", {}).get("value", "")
    app_base = nondurable.get("artifact_registry_app_url", {}).get("value", "")
    spark_image = args.spark_image or (f"{spark_base}:latest" if spark_base else "")
    app_image = args.app_image or (f"{app_base}:latest" if app_base else "")
    if not spark_image or not app_image:
        print("Error: artifact_registry_spark_url and artifact_registry_app_url required from nondurable. "
              "Run deploy without --skip-build first.", file=sys.stderr)
        raise SystemExit(1)

    pg_host = args.pg_host or durable.get("cloud_sql_private_ip", {}).get("value", "localhost")
    db_secret_id = args.db_secret_id or durable.get("db_password_plain_secret_id", {}).get("value", "")
    openai_secret_id = args.openai_secret_id or durable.get("openai_api_key_secret_id", {}).get("value", "")
    claude_secret_id = args.claude_secret_id or durable.get("claude_api_key_secret_id", {}).get("value", "")
    google_secret_id = args.google_secret_id or durable.get("google_ai_api_key_secret_id", {}).get("value", "")

    # Namespace
    _kubectl(["apply", "-f", "-"], input_text=f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {K8S_NAMESPACE}\n")

    if args.phase == "bootstrap":
        if not db_secret_id:
            print("Error: db_password_plain_secret_id required from durable. Ensure secrets are set up.", file=sys.stderr)
            raise SystemExit(1)
        try:
            pw = _fetch_gcp_secret(db_secret_id, project)
        except Exception as e:
            print(f"Error: Could not fetch db password from {db_secret_id}: {e}", file=sys.stderr)
            raise SystemExit(1)
        secret_b64 = base64.b64encode(pw.encode()).decode()
        _kubectl(["apply", "-f", "-"], input_text=f"""apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
  PGPASSWORD: {secret_b64}
""")

        def _fetch_or_fail(secret_id: str, name: str) -> str:
            try:
                return _fetch_gcp_secret(secret_id, project)
            except Exception as e:
                print(f"Error: Could not fetch {name} from {secret_id}: {e}", file=sys.stderr)
                raise SystemExit(1)

        openai_key = _fetch_or_fail(openai_secret_id, "OPENAI_API_KEY") if openai_secret_id else ""
        claude_key = _fetch_or_fail(claude_secret_id, "CLAUDE_API_KEY") if claude_secret_id else ""
        google_key = _fetch_or_fail(google_secret_id, "GOOGLE_AI_API_KEY") if google_secret_id else ""
        if not openai_key and not claude_key and not google_key:
            print("Error: At least one LLM key (OPENAI_API_KEY, CLAUDE_API_KEY, or GOOGLE_AI_API_KEY) required.", file=sys.stderr)
            raise SystemExit(1)
        app_data = {"OPENAI_API_KEY": base64.b64encode(openai_key.encode()).decode()}
        if claude_key:
            app_data["CLAUDE_API_KEY"] = base64.b64encode(claude_key.encode()).decode()
        if google_key:
            app_data["GOOGLE_AI_API_KEY"] = base64.b64encode(google_key.encode()).decode()
        data_lines = "\n".join(f"  {k}: {v}" for k, v in app_data.items())
        _kubectl(["apply", "-f", "-"], input_text=f"""apiVersion: v1
kind: Secret
metadata:
  name: app-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
{data_lines}
""")

        if not args.force and check_k8s_bootstrap_job_succeeded(args.env, region, "gcp"):
            print(f"[KUBE BOOTSTRAP] Skip: Job {JOB_BOOTSTRAP} already succeeded (idempotent)")
        else:
            delta_lake_pkg = require("DELTA_LAKE_PACKAGE")
            delta_storage_pkg = require("DELTA_STORAGE_PACKAGE")
            subs = {
                "cloud_provider": "gcp",
                "SPARK_IMAGE": spark_image,
                "DELTA_ROOT": delta_root,
                "DELTA_TABLE_PATH": delta_table_path,
                "DELTA_LAKE_PACKAGE": delta_lake_pkg,
                "DELTA_STORAGE_PACKAGE": delta_storage_pkg,
                "PGHOST": pg_host,
                "PGPORT": args.pg_port,
                "PGDATABASE": args.pg_database,
                "PGUSER": args.pg_user,
                "CLOUD_REGION": region,
            }
            txt = render("bootstrap-job", subs)
            _kubectl(["delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE])
            _kubectl(["apply", "-f", "-"], input_text=txt)

        interval_sec = get_required_analytics_scheduler_interval_seconds()
        delta_lake_pkg = require("DELTA_LAKE_PACKAGE")
        proxy_public_url = (kube_out.get("kube_base_url", {}).get("value") or "").strip()
        api_subs = {
            "cloud_provider": "gcp",
            "APP_IMAGE": app_image,
            "CONTAINER_TYPE": "gke",
            "DEPLOY_SCOPE": "kube",
            "CLOUD_PROVIDER": "gcp",
            "PGHOST": pg_host,
            "PGPORT": args.pg_port,
            "PGUSER": args.pg_user,
            "PGDATABASE": args.pg_database,
            "ALLOWED_ORIGINS": "*",
            "CLOUD_REGION": region,
            "DELTA_TABLE_PATH": delta_table_path,
            "DELTA_LAKE_PACKAGE": delta_lake_pkg,
            "SPARK_HOME": "/opt/spark",
            "GCP_LLM_PROVIDER": args.gcp_llm_provider,
            "CLAUDE_MODEL": args.claude_model,
            "GOOGLE_MODEL": args.google_model,
            "ENABLE_ANALYTICS_SCHEDULER": "true",
            "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": str(interval_sec),
            "APP_IMAGE_TAG": os.getenv("APP_IMAGE_TAG", ""),
            "PROXY_PUBLIC_URL": proxy_public_url,
        }
        _kubectl(["apply", "-f", "-"], input_text=render("api-deployment", api_subs))
        _kubectl(["apply", "-f", "-"], input_text=render("api-service", {"cloud_provider": "gcp"}))

    else:
        interval_sec = get_required_analytics_scheduler_interval_seconds()
        subs = {
            "cloud_provider": "gcp",
            "SPARK_IMAGE": spark_image,
            "DELTA_ROOT": delta_root,
            "DELTA_TABLE_PATH": delta_table_path,
            "SCHEDULE_CRON": seconds_to_cron(interval_sec),
            "PGHOST": pg_host,
            "PGPORT": args.pg_port,
            "PGDATABASE": args.pg_database,
            "PGUSER": args.pg_user,
            "CLOUD_REGION": region,
        }
        _kubectl(["apply", "-f", "-"], input_text=render("spark-cronjob", subs))


if __name__ == "__main__":
    main()
