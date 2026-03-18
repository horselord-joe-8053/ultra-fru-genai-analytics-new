
"""
Apply Kubernetes manifests (bootstrap + schedule) to EKS.

Examples:
  python tools/aws/kube/kube_apply.py --env dev --phase bootstrap
  python tools/aws/kube/kube_apply.py --env dev --phase schedule

This tool:
- ensures kubeconfig for EKS
- creates namespace `fru-kube`
- substitutes SPARK_IMAGE, DELTA_ROOT, PG*
- applies Job/CronJob manifests
"""
import argparse, base64, json, os, subprocess, time
import sys
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from tools.cloud_shared.analytics_schedule import (
    get_required_analytics_scheduler_interval_seconds,
    seconds_to_cron,
)
from tools.cloud_shared.env import load_dotenv, require
from tools.cloud_shared.k8s_j2_render import render
from tools.aws.scope_shared.core.backend import resolve_region
from tools.aws.scope_shared.deploy.k8s_deploy_helpers import check_k8s_bootstrap_job_succeeded, JOB_BOOTSTRAP, K8S_NAMESPACE

load_dotenv()

def kubectl(args, input_text=None):
    cmd = ["kubectl"] + args
    print("+", " ".join(cmd))
    subprocess.run(cmd, input=input_text, text=True, check=False)


_WEBHOOK_NO_ENDPOINTS = "no endpoints available for service \"aws-load-balancer-webhook-service\""


def _kubectl_apply_with_webhook_retry(input_text: str, max_attempts: int = 6, interval_sec: int = 30) -> bool:
    """Apply manifest with retry when AWS LB Controller webhook has no endpoints yet.
    Returns True if applied successfully, False if all retries failed."""
    for attempt in range(max_attempts):
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=input_text,
            text=True,
            capture_output=True,
        )
        stdout, stderr = result.stdout or "", result.stderr or ""
        combined = stdout + stderr
        if result.returncode == 0:
            return True
        if _WEBHOOK_NO_ENDPOINTS in combined:
            if attempt < max_attempts - 1:
                print(f"  [retry {attempt + 1}/{max_attempts}] Webhook not ready; waiting {interval_sec}s...")
                time.sleep(interval_sec)
            else:
                print(f"  [FAIL] Webhook still not ready after {max_attempts} attempts.")
                print(stderr)
                return False
        else:
            print(stderr)
            return False
    return False

def fetch_secret_value(secret_arn: str) -> str:
    """Fetch secret value from AWS Secrets Manager. Handles plain string or JSON."""
    out = subprocess.check_output([
        "aws", "secretsmanager", "get-secret-value",
        "--secret-id", secret_arn,
        "--query", "SecretString",
        "--output", "text",
        "--region", os.getenv("CLOUD_REGION", "").strip() or require("CLOUD_REGION"),
    ], text=True)
    raw = out.strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, str) else str(parsed)
    except json.JSONDecodeError:
        return raw.strip('"')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--phase", choices=["bootstrap","schedule"], required=True)
    ap.add_argument("--spark-image", help="Full Spark image URI")
    ap.add_argument("--app-image", help="Full App image URI")
    ap.add_argument("--delta-bucket", help="S3 delta bucket (overrides S3_DELTA_COMPONENT / resource_names.s3_delta_bucket)")
    ap.add_argument("--pg-host", default="", help="PGHOST from durable")
    ap.add_argument("--pg-port", default="5432", help="PGPORT")
    ap.add_argument("--pg-database", default="fru_db", help="PGDATABASE")
    ap.add_argument("--pg-user", default="postgres", help="PGUSER")
    ap.add_argument("--db-secret-arn", default="", help="AWS Secrets Manager ARN for db_password")
    ap.add_argument("--openai-secret-arn", default="", help="AWS Secrets Manager ARN for openai_api_key")
    ap.add_argument("--aws-region", default="", help="Region for pods (CLOUD_REGION)")
    ap.add_argument("--delta-table-path", default="", help="DELTA_TABLE_PATH (s3a://bucket/delta/fru_sales)")
    ap.add_argument("--delta-lake-package", default=None, help="DELTA_LAKE_PACKAGE")
    ap.add_argument("--bedrock-inference-profile-id", default="", help="AWS_BEDROCK_INFERENCE_PROFILE_ID")
    ap.add_argument("--bedrock-model-id", default="", help="AWS_BEDROCK_MODEL_ID from .env (required if no inference profile)")
    ap.add_argument("--force", action="store_true", help="Force bootstrap even if already succeeded (e.g. after CSV upload)")
    ap.add_argument("--elb", action="store_true", help="Use in-tree Classic ELB instead of NLB (api-service template)")
    args = ap.parse_args()

    # Bedrock: require model id from .env when inference profile not set
    if not args.bedrock_inference_profile_id and not args.bedrock_model_id:
        from core_app.backend.env_utils.cloud_shared.model_config import require_bedrock_model_id
        args.bedrock_model_id = require_bedrock_model_id()
    elif not args.bedrock_model_id:
        args.bedrock_model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "").strip()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    from tools.aws.scope_shared.core import resource_names

    # ensure kubeconfig
    subprocess.run(["python","tools/aws/kube/eks_kubeconfig.py","--env",args.env], check=False, env={**os.environ, "CLOUD_REGION": region})

    spark_image = args.spark_image
    if not spark_image:
        tag = os.getenv("SPARK_IMAGE_TAG", "latest")
        spark_image = resource_names.ecr_image_uri("spark", args.env, region, tag)

    app_image = args.app_image
    if not app_image:
        tag = os.getenv("APP_IMAGE_TAG", "latest")
        app_image = resource_names.ecr_image_uri("app", args.env, region, tag)

    delta_bucket = args.delta_bucket or resource_names.s3_delta_bucket(args.env, region)
    delta_root = f"s3a://{delta_bucket}/delta"

    # namespace
    kubectl(["apply","-f","-"], input_text=f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {K8S_NAMESPACE}\n")

    if args.phase == "bootstrap":
        # Create db-credentials secret first (Job references it via secretKeyRef)
        pw = "placeholder"
        if args.db_secret_arn:
            try:
                pw = fetch_secret_value(args.db_secret_arn)
            except Exception as e:
                print(f"WARN: Could not fetch db password: {e}")
        secret_b64 = base64.b64encode(pw.encode()).decode()
        secret_yml = f"""apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
  PGPASSWORD: {secret_b64}
"""
        kubectl(["apply", "-f", "-"], input_text=secret_yml)

        # Create app-credentials secret (OPENAI_API_KEY from AWS or placeholder)
        openai_key = "sk-placeholder"
        if args.openai_secret_arn:
            try:
                openai_key = fetch_secret_value(args.openai_secret_arn)
            except Exception as e:
                print(f"WARN: Could not fetch OPENAI_API_KEY: {e}")
        openai_b64 = base64.b64encode(openai_key.encode()).decode()
        app_secret_yml = f"""apiVersion: v1
kind: Secret
metadata:
  name: app-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
  OPENAI_API_KEY: {openai_b64}
"""
        kubectl(["apply", "-f", "-"], input_text=app_secret_yml)

        # AWS credentials for Bedrock (agent) and S3 (analytics scheduler)
        aws_access = os.getenv("AWS_ADMIN_ACCESS_KEY_ID") or os.getenv("AWS_BEDROCK_ACCESS_KEY_ID") or ""
        aws_secret = os.getenv("AWS_ADMIN_SECRET_ACCESS_KEY") or os.getenv("AWS_BEDROCK_SECRET_ACCESS_KEY") or ""
        if aws_access and aws_secret:
            aws_access_b64 = base64.b64encode(aws_access.encode()).decode()
            aws_secret_b64 = base64.b64encode(aws_secret.encode()).decode()
            aws_creds_yml = f"""apiVersion: v1
kind: Secret
metadata:
  name: aws-credentials
  namespace: {K8S_NAMESPACE}
type: Opaque
data:
  AWS_ACCESS_KEY_ID: {aws_access_b64}
  AWS_SECRET_ACCESS_KEY: {aws_secret_b64}
"""
            kubectl(["apply", "-f", "-"], input_text=aws_creds_yml)
        else:
            print("WARN: AWS_ADMIN_ACCESS_KEY_ID/SECRET or AWS_BEDROCK_* not set; agent Bedrock calls may fail")

        if not args.force and check_k8s_bootstrap_job_succeeded(args.env, region):
            print(f"[KUBE BOOTSTRAP] Skip: Job {JOB_BOOTSTRAP} already succeeded (idempotent)")
        else:
            delta_table_path = args.delta_table_path or f"s3a://{delta_bucket}/delta/fru_sales"
            delta_lake_pkg = args.delta_lake_package or require("DELTA_LAKE_PACKAGE")
            delta_storage_pkg = require("DELTA_STORAGE_PACKAGE")
            hadoop_pkg = require("HADOOP_PACKAGE")
            subs = {
                "cloud_provider": "aws",
                "SPARK_IMAGE": spark_image,
                "DELTA_ROOT": delta_root,
                "DELTA_TABLE_PATH": delta_table_path,
                "DELTA_LAKE_PACKAGE": delta_lake_pkg,
                "DELTA_STORAGE_PACKAGE": delta_storage_pkg,
                "HADOOP_PACKAGE": hadoop_pkg,
                "PGHOST": args.pg_host or "localhost",
                "PGPORT": args.pg_port,
                "PGDATABASE": args.pg_database,
                "PGUSER": args.pg_user,
                "AWS_ACCESS_KEY_ID": require("AWS_ADMIN_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY": require("AWS_ADMIN_SECRET_ACCESS_KEY"),
                "CLOUD_REGION": os.getenv("CLOUD_REGION", "").strip() or require("CLOUD_REGION")
            }
            txt = render("bootstrap-job", subs)
            kubectl(["delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE])
            kubectl(["apply", "-f", "-"], input_text=txt)

        # Deploy API (always run - idempotent)
        try:
            interval_sec = get_required_analytics_scheduler_interval_seconds()
            delta_table_path = args.delta_table_path or f"s3a://{delta_bucket}/delta/fru_sales"
            api_subs = {
                "cloud_provider": "aws",
                "APP_IMAGE": app_image,
                "APP_IMAGE_TAG": os.getenv("APP_IMAGE_TAG", ""),
                "CONTAINER_TYPE": "eks",
                "DEPLOY_SCOPE": "kube",
                "CLOUD_PROVIDER": "aws",
                "PGHOST": args.pg_host or "localhost",
                "PGPORT": args.pg_port,
                "PGUSER": args.pg_user,
                "PGDATABASE": args.pg_database,
                "ALLOWED_ORIGINS": "*",
                "CLOUD_REGION": args.aws_region or os.getenv("CLOUD_REGION", "").strip() or require("CLOUD_REGION"),
                "DELTA_TABLE_PATH": delta_table_path,
                "DELTA_LAKE_PACKAGE": args.delta_lake_package,
                "SPARK_HOME": "/opt/spark",
                "AWS_BEDROCK_INFERENCE_PROFILE_ID": args.bedrock_inference_profile_id or os.getenv("AWS_BEDROCK_INFERENCE_PROFILE_ID", ""),
                "AWS_BEDROCK_MODEL_ID": args.bedrock_model_id or os.getenv("AWS_BEDROCK_MODEL_ID", ""),
                "AWS_BEDROCK_REGION": os.getenv("AWS_BEDROCK_REGION", "us-east-1").strip(),
                "ENABLE_ANALYTICS_SCHEDULER": os.getenv("ENABLE_ANALYTICS_SCHEDULER", "true"),
                "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": str(interval_sec),
            }
            txt = render("api-deployment", api_subs)
            kubectl(["apply","-f","-"], input_text=txt)
            txt = render("api-service", {"cloud_provider": "aws", "use_elb": args.elb})
            if args.elb:
                kubectl(["apply","-f","-"], input_text=txt)
            else:
                # NLB requires AWS LB Controller webhook; retry when webhook pods not ready yet
                print("+ kubectl apply -f - (api-service, with webhook retry)")
                if not _kubectl_apply_with_webhook_retry(txt):
                    raise SystemExit(1)
        except FileNotFoundError:
            print("WARN: API manifests not found, skipping API deployment.")
    else:
        # Schedule phase: apply CronJob. Requires aws-credentials secret from bootstrap for S3 access.
        interval_sec = get_required_analytics_scheduler_interval_seconds()
        delta_table_path = args.delta_table_path or f"s3a://{delta_bucket}/delta/fru_sales"
        delta_lake_pkg = args.delta_lake_package or require("DELTA_LAKE_PACKAGE")
        delta_storage_pkg = require("DELTA_STORAGE_PACKAGE")
        hadoop_pkg = require("HADOOP_PACKAGE")
        subs = {
            "cloud_provider": "aws",
            "SPARK_IMAGE": spark_image,
            "DELTA_ROOT": delta_root,
            "DELTA_TABLE_PATH": delta_table_path,
            "DELTA_LAKE_PACKAGE": delta_lake_pkg,
            "DELTA_STORAGE_PACKAGE": delta_storage_pkg,
            "HADOOP_PACKAGE": hadoop_pkg,
            "SCHEDULE_CRON": seconds_to_cron(interval_sec),
            "PGHOST": args.pg_host or "localhost",
            "PGPORT": args.pg_port,
            "PGDATABASE": args.pg_database,
            "PGUSER": args.pg_user,
            "CLOUD_REGION": args.aws_region or os.getenv("CLOUD_REGION", "").strip() or require("CLOUD_REGION"),
        }
        txt = render("spark-cronjob", subs)
        kubectl(["apply","-f","-"], input_text=txt)

if __name__ == "__main__":
    main()
