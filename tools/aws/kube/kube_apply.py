
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
import argparse, base64, json, os, subprocess
from tools.cloud_shared.env import load_dotenv, require
from tools.aws.scope_shared.core.backend import resolve_region
from tools.aws.scope_shared.deploy.bootstrap_helpers import check_k8s_bootstrap_job_succeeded, JOB_BOOTSTRAP, K8S_NAMESPACE

load_dotenv()

def render(template_path, subs):
    s = open(template_path, "r").read()
    for k,v in subs.items():
        s = s.replace("${"+k+"}", str(v))
    return s

def kubectl(args, input_text=None):
    cmd = ["kubectl"] + args
    print("+", " ".join(cmd))
    subprocess.run(cmd, input=input_text, text=True, check=False)

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
    ap.add_argument("--delta-bucket", help="S3 delta bucket (overrides S3_DELTA_BUCKET)")
    ap.add_argument("--pg-host", default="", help="PGHOST from durable")
    ap.add_argument("--pg-port", default="5432", help="PGPORT")
    ap.add_argument("--pg-database", default="fru_db", help="PGDATABASE")
    ap.add_argument("--pg-user", default="postgres", help="PGUSER")
    ap.add_argument("--db-secret-arn", default="", help="AWS Secrets Manager ARN for db_password")
    ap.add_argument("--openai-secret-arn", default="", help="AWS Secrets Manager ARN for openai_api_key")
    ap.add_argument("--aws-region", default="", help="Region for pods (CLOUD_REGION)")
    ap.add_argument("--delta-table-path", default="", help="DELTA_TABLE_PATH (s3a://bucket/delta/fru_sales)")
    ap.add_argument("--delta-lake-package", default="io.delta:delta-spark_2.13:4.0.0", help="DELTA_LAKE_PACKAGE")
    ap.add_argument("--bedrock-inference-profile-id", default="", help="AWS_BEDROCK_INFERENCE_PROFILE_ID")
    ap.add_argument("--bedrock-model-id", default="anthropic.claude-3-5-haiku-20241022-v1:0", help="AWS_BEDROCK_MODEL_ID")
    ap.add_argument("--force", action="store_true", help="Force bootstrap even if already succeeded (e.g. after CSV upload)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    # ensure kubeconfig
    subprocess.run(["python","tools/aws/kube/eks_kubeconfig.py","--env",args.env], check=False, env={**os.environ, "CLOUD_REGION": region})

    spark_image = args.spark_image
    if not spark_image:
        spark_image = f"{require('ECR_REPO_SPARK')}:{require('SPARK_IMAGE_TAG')}"

    app_image = args.app_image
    if not app_image:
        app_image = f"{require('ECR_REPO_APP')}:{require('APP_IMAGE_TAG')}"

    delta_bucket = args.delta_bucket or os.getenv("S3_DELTA_BUCKET") or f"{os.getenv('FRU_PREFIX','fru')}-{args.env}-delta"
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

        if not args.force and check_k8s_bootstrap_job_succeeded(args.env):
            print(f"[KUBE BOOTSTRAP] Skip: Job {JOB_BOOTSTRAP} already succeeded (idempotent)")
        else:
            delta_table_path = args.delta_table_path or f"s3a://{delta_bucket}/delta/fru_sales"
            subs = {
                "SPARK_IMAGE": spark_image,
                "DELTA_ROOT": delta_root,
                "DELTA_TABLE_PATH": delta_table_path,
                "PGHOST": args.pg_host or "localhost",
                "PGPORT": args.pg_port,
                "PGDATABASE": args.pg_database,
                "PGUSER": args.pg_user,
                "AWS_ACCESS_KEY_ID": require("AWS_ADMIN_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY": require("AWS_ADMIN_SECRET_ACCESS_KEY"),
                "CLOUD_REGION": os.getenv("CLOUD_REGION", "").strip() or require("CLOUD_REGION")
            }
            txt = render("infra_terraform/modules/cloud_shared/k8s/bootstrap-job.yaml", subs)
            kubectl(["delete", "job", JOB_BOOTSTRAP, "--ignore-not-found", "-n", K8S_NAMESPACE])
            kubectl(["apply", "-f", "-"], input_text=txt)

        # Deploy API (always run - idempotent)
        try:
            delta_table_path = args.delta_table_path or f"s3a://{delta_bucket}/delta/fru_sales"
            api_subs = {
                "APP_IMAGE": app_image,
                "CONTAINER_IMAGE_TAGS": os.getenv("CONTAINER_IMAGE_TAGS", ""),
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
                "AWS_BEDROCK_MODEL_ID": args.bedrock_model_id or os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"),
                "ENABLE_ANALYTICS_SCHEDULER": os.getenv("ENABLE_ANALYTICS_SCHEDULER", "true"),
                "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": os.getenv("ANALYTICS_SCHEDULER_INTERVAL_SECONDS", "180"),
            }
            txt = render("infra_terraform/modules/cloud_shared/k8s/api-deployment.yaml", api_subs)
            kubectl(["apply","-f","-"], input_text=txt)
            txt = render("infra_terraform/modules/cloud_shared/k8s/api-service.yaml", {})
            kubectl(["apply","-f","-"], input_text=txt)
        except FileNotFoundError:
            print("WARN: API manifests not found, skipping API deployment.")
    else:
        delta_table_path = args.delta_table_path or f"s3a://{delta_bucket}/delta/fru_sales"
        subs = {
            "SPARK_IMAGE": spark_image,
            "DELTA_ROOT": delta_root,
            "DELTA_TABLE_PATH": delta_table_path,
            "PGHOST": args.pg_host or "localhost",
            "PGPORT": args.pg_port,
            "PGDATABASE": args.pg_database,
            "PGUSER": args.pg_user,
        }
        txt = render("infra_terraform/modules/cloud_shared/k8s/spark-cronjob.yaml", subs)
        kubectl(["apply","-f","-"], input_text=txt)

if __name__ == "__main__":
    main()
