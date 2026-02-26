
"""
Preflight checks for AWS deploy/teardown.

Usage:
  python tools/aws/standalone/doctor.py --env dev

Legacy-aware:
- Accepts AWS_PROFILE (optional). If set, AWS CLI uses it naturally.
"""
import argparse, os, subprocess, json, shutil, sys
from tools.cloud_shared.env import load_dotenv, require, EnvVarNotFound
from tools.aws.scope_shared.core.backend import resolve_region

load_dotenv()

# Ensure common paths in PATH so brew-installed tools (eksctl, helm, kubectl) are found
for p in ("/usr/local/bin", "/opt/homebrew/bin"):
    if os.path.isdir(p) and p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

def has(exe):
    """Return True if executable exists and runs. Handles tools that use 'version' not '--version'."""
    if not shutil.which(exe):
        return False
    try:
        # eksctl, helm use 'version' not '--version'
        flag = "version" if exe in ("eksctl", "helm") else "--version"
        subprocess.check_output([exe, flag], stderr=subprocess.STDOUT, text=True)
        return True
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("ENVIRONMENT", os.getenv("FRU_ENV","dev")))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default=None, help="Deploy scope (kube requires kubectl)")
    ap.add_argument("--elb", action="store_true", help="[Kube only] Use Classic ELB; skip eksctl/helm check (NLB track needs them)")
    args = ap.parse_args()

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    os.environ["CLOUD_REGION"] = region

    # APP_IMAGE_TAG and SPARK_IMAGE_TAG are optional; deploy auto-generates when commented out in .env
    # TF_STATE_BUCKET_COMPONENT + TF_LOCK_TABLE_COMPONENT (preferred) or TF_STATE_BUCKET_PREFIX / TF_STATE_BUCKET
    if os.getenv("TF_STATE_BUCKET_COMPONENT"):
        if not os.getenv("TF_LOCK_TABLE_COMPONENT"):
            require("TF_LOCK_TABLE_COMPONENT")
    elif os.getenv("TF_STATE_BUCKET_PREFIX"):
        require("TF_LOCK_TABLE_PREFIX")
    else:
        require("TF_STATE_BUCKET")
    # PROJ_PREFIX (or FRU_PREFIX during transition); *_COMPONENT vars for resource naming
    if not (os.getenv("PROJ_PREFIX") or os.getenv("FRU_PREFIX")):
        require("PROJ_PREFIX")
    # Component vars (or legacy full-name vars)
    if not (os.getenv("S3_DELTA_COMPONENT") or os.getenv("S3_DELTA_BUCKET")):
        require("S3_DELTA_COMPONENT")
    if not (os.getenv("S3_ARTIFACT_COMPONENT") or os.getenv("S3_ARTIFACT_BUCKET")):
        require("S3_ARTIFACT_COMPONENT")
    if not (os.getenv("ECR_APP_COMPONENT") or os.getenv("ECR_REPO_APP")):
        require("ECR_APP_COMPONENT")
    if not (os.getenv("ECR_SPARK_COMPONENT") or os.getenv("ECR_REPO_SPARK")):
        require("ECR_SPARK_COMPONENT")

    tfbin = os.getenv("FRU_TF_BIN","tofu")
    if not has("aws"):
        raise SystemExit("Missing required executable: aws")
    if not has(tfbin):
        raise SystemExit(f"Missing required executable: {tfbin}")
    if not has("docker"):
        raise SystemExit("Missing required executable: docker")

    # Only warn about kubectl when scope needs it (kube or all); skip for nonkube
    if args.scope != "nonkube":
        if not (shutil.which("kubectl") or has("kubectl")):
            print("WARN: kubectl not found (kube deploy will fail until installed).")

    # NLB track (kube/all without --elb) requires eksctl and helm for AWS Load Balancer Controller install
    if args.scope in ("kube", "all") and not args.elb:
        if not has("eksctl"):
            raise SystemExit("Missing required executable: eksctl (install via: brew install eksctl). Required for NLB track.")
        if not has("helm"):
            raise SystemExit("Missing required executable: helm (install via: brew install helm). Required for NLB track.")

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
