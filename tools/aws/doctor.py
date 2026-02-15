
"""
Preflight checks for AWS deploy/teardown.

Usage:
  python tools/aws/doctor.py --env dev

Legacy-aware:
- Accepts AWS_PROFILE (optional). If set, AWS CLI uses it naturally.
"""
import argparse, os, subprocess, json
from tools._env import load_dotenv, require
from tools.aws._backend import resolve_region

load_dotenv()

def has(exe):
    try:
        subprocess.check_output([exe, "--version"], stderr=subprocess.STDOUT, text=True)
        return True
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("ENVIRONMENT", os.getenv("FRU_ENV","dev")))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    os.environ["AWS_REGION"] = region

    for k in ["TF_STATE_BUCKET","FRU_PREFIX","S3_DELTA_BUCKET","S3_ARTIFACT_BUCKET","ECR_REPO_APP","ECR_REPO_SPARK","APP_IMAGE_TAG","SPARK_IMAGE_TAG"]:
        require(k)

    tfbin = os.getenv("FRU_TF_BIN","tofu")
    if not has("aws"):
        raise SystemExit("Missing required executable: aws")
    if not has(tfbin):
        raise SystemExit(f"Missing required executable: {tfbin}")
    if not has("docker"):
        raise SystemExit("Missing required executable: docker")

    if not has("kubectl"):
        print("WARN: kubectl not found (kube deploy will fail until installed).")

    try:
        out = subprocess.check_output(["aws","sts","get-caller-identity"], text=True)
        ident = json.loads(out)
        print("AWS Account:", ident.get("Account"))
        print("AWS Arn:", ident.get("Arn"))
    except Exception as e:
        raise SystemExit(f"AWS credentials not working: {e}")

    print("Doctor OK.")

if __name__ == "__main__":
    main()
