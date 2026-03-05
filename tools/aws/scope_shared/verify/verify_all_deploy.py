"""
AWS deployment verification.

Phases: Endpoints (nonkube/kube) + local LLM client. No CloudWatch; ETL self-check verifies DB.
Uses tools/cloud_shared/verify for shared logic (verify_api_endpoints, verify_csv, verify_llm_client).
"""
import json
import os
import subprocess
import sys
import time

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
load_dotenv()

from tools.cloud_shared.logging import logger
from tools.cloud_shared.verify.verify_all_deploy_common import run_verify_all_deploy
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.core.terra_runner import ensure_shared_terra_env
from tools.aws.scope_shared.deploy.deploy_common import init_stack
from tools.aws.scope_shared.core.backend import resolve_region

print("verify_all_deploy: imports done, entering main()", flush=True)


def get_tofu_output(stack_dir: str, env: str) -> dict:
    """Retrieve output from Tofu (assumed already applied). AWS-specific: init_stack, region."""
    ensure_shared_terra_env()
    region = resolve_region(None)
    try:
        init_stack(stack_dir, env, region)
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=stack_dir, text=True, env={**os.environ, "CLOUD_REGION": region}
        )
        return json.loads(out)
    except Exception as e:
        logger.warning(f"could not get tofu output from {stack_dir}: {e}")
        return {}


def _extract_base_url_aws(scope: str, stack_out: dict) -> str | None:
    """Extract base_url from AWS tofu outputs."""
    if scope == "nonkube":
        cf = stack_out.get("cloudfront_domain_name", {}).get("value")
        alb = stack_out.get("alb_dns_name", {}).get("value")
        if cf:
            return f"https://{cf}"
        if alb:
            return f"http://{alb}"
        return None
    if scope == "kube":
        cf = stack_out.get("cloudfront_domain_name", {}).get("value")
        if cf:
            return f"https://{cf}"
        return None
    return None


def _kube_fallback_aws(env: str, region: str) -> str | None:
    """AWS kube: when CloudFront not ready, poll EKS LoadBalancer hostname."""
    from tools.aws.kube.deploy_kube import _try_get_lb_hostname
    logger.info("Waiting for EKS LoadBalancer hostname...")
    subprocess.run(
        ["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env],
        check=False,
        env={**os.environ, "CLOUD_REGION": region},
    )
    for _ in range(30):
        lb_host = _try_get_lb_hostname(env, region)
        if lb_host:
            return f"http://{lb_host}"
        time.sleep(10)
    logger.warning("EKS LoadBalancer hostname not available after timeout. Skipping endpoint check (kube).")
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", required=True, help="Cloud region. Required.")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    args = ap.parse_args()
    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)

    os.environ.setdefault("CLOUD_PROVIDER", "aws")

    run_verify_all_deploy(
        provider="aws",
        env=args.env,
        region=region,
        scope=args.scope,
        get_tofu_output_fn=get_tofu_output,
        extract_base_url=_extract_base_url_aws,
        kube_fallback_fn=_kube_fallback_aws,
        setup_fn=lambda: get_base_vars(args.env),
    )


if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
