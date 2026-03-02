"""
GCP preflight checks (reference: tools/aws/standalone/doctor.py).

Usage:
  python tools/gcp/standalone/doctor.py --env dev
  python orchestrator.py doctor --provider gcp
"""
import argparse
import os
import subprocess
import sys
import shutil

# Add project root for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.cloud_shared.env import load_dotenv, require, EnvVarNotFound

load_dotenv()


def _resolve_region(arg_region: str) -> str:
    """Resolve region from arg or CLOUD_REGION."""
    if arg_region:
        return arg_region
    r = os.environ.get("CLOUD_REGION", "").strip()
    if r:
        return r
    raise EnvVarNotFound("CLOUD_REGION", "Set in .env or pass --region")


def has(exe: str) -> bool:
    """Return True if executable exists and runs."""
    if not shutil.which(exe):
        return False
    for flag in ("--version", "version"):
        try:
            subprocess.check_output([exe, flag], stderr=subprocess.STDOUT, text=True)
            return True
        except Exception:
            continue
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    try:
        region = _resolve_region(args.region)
    except EnvVarNotFound as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    os.environ["CLOUD_REGION"] = region

    require("GCP_PROJECT_ID")
    if not (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    ):
        raise SystemExit(
            "Error: GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON must be set."
        )

    if not has("gcloud"):
        raise SystemExit("Missing required executable: gcloud (install via: brew install google-cloud-sdk)")

    tfbin = os.getenv("FRU_TF_BIN", "tofu")
    if not has(tfbin):
        raise SystemExit(f"Missing required executable: {tfbin}")

    if not has("docker"):
        raise SystemExit("Missing required executable: docker")

    try:
        out = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        proj = out.strip()
        if proj and proj != "(unset)":
            print("GCP Project:", proj)
        print("GCP Region:", region)
    except Exception as e:
        raise SystemExit(f"gcloud config check failed: {e}")

    print("Doctor OK.")


if __name__ == "__main__":
    main()
