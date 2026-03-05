"""
GCP deployment verification.

Phases: Endpoints (nonkube/kube) + local LLM client. No Cloud Logging; ETL self-check verifies DB.
Uses tools/cloud_shared/verify for shared logic (verify_api_endpoints, verify_csv, verify_llm_client).
"""
import os
import sys

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
load_dotenv()
from tools.gcp.scope_shared.deploy.bootstrap_state_backend import load_gcp_env
load_gcp_env()  # Fix multi-line GOOGLE_APPLICATION_CREDENTIALS_JSON for tofu subprocess

from tools.cloud_shared.logging import logger
from tools.cloud_shared.verify.verify_all_deploy_common import run_verify_all_deploy
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.gcp.scope_shared.core.terra_runner import get_terra_env
from tools.gcp.scope_shared.core.terra_init import init_stack

print("verify_all_deploy: imports done, entering main()", flush=True)


def get_tofu_output(stack_dir: str, env: str) -> dict:
    """Retrieve output from Tofu (assumed already applied). GCP-specific: init_stack, get_terra_env."""
    import json
    import subprocess
    region = resolve_region(None)
    try:
        init_stack(stack_dir, env, region)
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=stack_dir,
            text=True,
            env={**get_terra_env(region), "CLOUD_REGION": region},
        )
        return json.loads(out)
    except Exception as e:
        logger.warning(f"could not get tofu output from {stack_dir}: {e}")
        return {}


def _extract_base_url_gcp(scope: str, stack_out: dict) -> str | None:
    """Extract base_url from GCP tofu outputs."""
    if scope == "nonkube":
        url = stack_out.get("cloud_run_url", {}).get("value") or stack_out.get("service_url", {}).get("value")
        return url
    if scope == "kube":
        url = stack_out.get("kube_base_url", {}).get("value")
        if url:
            return url
        cdn = stack_out.get("cloudfront_domain_name", {}).get("value")
        if cdn:
            return f"http://{cdn}"
        return None
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="kube")
    args = ap.parse_args()

    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)

    os.environ["CLOUD_REGION"] = region
    os.environ["CLOUD_PROVIDER"] = "gcp"

    run_verify_all_deploy(
        provider="gcp",
        env=args.env,
        region=region,
        scope=args.scope,
        get_tofu_output_fn=get_tofu_output,
        extract_base_url=_extract_base_url_gcp,
        kube_fallback_fn=None,
        setup_fn=None,
    )


if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
