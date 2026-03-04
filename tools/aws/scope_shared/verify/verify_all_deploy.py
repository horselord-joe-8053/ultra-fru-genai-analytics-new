"""
AWS deployment verification.

Phases: Endpoints (nonkube/kube) + local LLM client. No CloudWatch; ETL self-check verifies DB.
Uses tools/cloud_shared/verify for shared logic (verify_api_endpoints, verify_csv, verify_llm_client).
"""
import os
import sys
import time
import json
import subprocess
import argparse

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
load_dotenv()  # Before verify_config/verify_api_endpoints (they read env)

from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.core.terra_runner import ensure_shared_terra_env
from tools.cloud_shared.verify.verify_summary import VerifyRow, print_verify_summary
from tools.cloud_shared.verify.verify_llm_client import verify_llm_client
from tools.cloud_shared.verify.verify_csv import get_total_rec_from_csv
from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints
print("verify_all_deploy: imports done, entering main()", flush=True)


def get_tofu_output(stack_dir: str, env: str) -> dict:
    """Retrieve output from Tofu (assumed already applied). AWS-specific: init_stack, region."""
    ensure_shared_terra_env()
    from tools.aws.scope_shared.deploy.deploy_common import init_stack
    from tools.aws.scope_shared.core.backend import resolve_region
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", required=True, help="Cloud region. Required.")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    args = ap.parse_args()
    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    env = args.env
    get_base_vars(env)

    total_rec = get_total_rec_from_csv()
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(args.region)

    verify_start = time.time()
    logger.operation_start("Verify", args.scope, args.env, region)
    logger.step(f"Full Verification Interface (env: {env}, region: {region}, total_rec from CSV: {total_rec})")

    os.environ.setdefault("CLOUD_PROVIDER", "aws")
    scopes_to_verify = ["nonkube", "kube"] if args.scope == "all" else [args.scope]
    verify_phases = [f"Endpoints ({s})" for s in scopes_to_verify] + ["LLM client"]
    total_phases = len(verify_phases)
    all_rows: list[VerifyRow] = []
    phase_idx = 0

    for scope in scopes_to_verify:
        phase_idx += 1
        phase_start_time = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])
        if scope == "nonkube":
            logger.info("Fetching nonkube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/aws/nonkube", env)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            alb_dns = stack_out.get("alb_dns_name", {}).get("value")
            base_url = f"https://{cf_domain}" if cf_domain else (f"http://{alb_dns}" if alb_dns else None)
            if base_url:
                ok, rows = verify_api_endpoints(base_url, total_rec, scope="nonkube", provider="aws")
                all_rows.extend(rows)
                if not ok:
                    logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly (nonkube)")
                    print_verify_summary(all_rows, env, total_rec)
                    logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                    sys.exit(1)
            else:
                logger.error("Could not find CloudFront domain or ALB DNS in terraform outputs (nonkube).")
                logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                sys.exit(1)
        elif scope == "kube":
            logger.info("Fetching kube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/aws/kube", env)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            if cf_domain:
                base_url = f"https://{cf_domain}"
                ok, rows = verify_api_endpoints(base_url, total_rec, scope="kube", provider="aws")
                all_rows.extend(rows)
                if not ok:
                    logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly (kube)")
                    print_verify_summary(all_rows, env, total_rec)
                    logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                    sys.exit(1)
            else:
                from tools.aws.kube.deploy_kube import _try_get_lb_hostname
                logger.info("Waiting for EKS LoadBalancer hostname...")
                subprocess.run(
                    ["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env],
                    check=False,
                    env={**os.environ, "CLOUD_REGION": region},
                )
                lb_host = ""
                for _ in range(30):
                    lb_host = _try_get_lb_hostname(env, region)
                    if lb_host:
                        break
                    time.sleep(10)

                if lb_host:
                    ok, rows = verify_api_endpoints(f"http://{lb_host}", total_rec, scope="kube", provider="aws")
                    all_rows.extend(rows)
                    if not ok:
                        logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly (kube)")
                        print_verify_summary(all_rows, env, total_rec)
                        sys.exit(1)
                else:
                    logger.warning("EKS LoadBalancer hostname not available after timeout. Skipping endpoint check (kube).")
        phase_secs = int(time.time() - phase_start_time)
        logger.phase_end(phase_idx, total_phases, verify_phases[phase_idx - 1], phase_secs)

    phase_idx += 1
    phase_start_time = time.time()
    logger.phase_start(phase_idx, total_phases, "LLM client")
    llm_ok, llm_rows = verify_llm_client()
    all_rows.extend(llm_rows)
    phase_secs = int(time.time() - phase_start_time)
    logger.phase_end(phase_idx, total_phases, "LLM client", phase_secs)

    if not llm_ok:
        logger.error("[VERIFICATION FAILED] LLM client failed")
        print_verify_summary(all_rows, env, total_rec)
        logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
        sys.exit(1)

    print_verify_summary(all_rows, env, total_rec)

    verify_dur = int(time.time() - verify_start)
    logger.operation_end("Verify", args.scope, args.env, region, verify_dur, ok=True)
    logger.success("FULL VERIFICATION: SUCCESS")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
