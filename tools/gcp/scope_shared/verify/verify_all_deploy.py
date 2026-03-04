"""
GCP deployment verification.

Phases: Endpoints (nonkube/kube) + local LLM client. No Cloud Logging; ETL self-check verifies DB.
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
from tools.gcp.scope_shared.deploy.bootstrap_state_backend import load_gcp_env
load_gcp_env()  # Fix multi-line GOOGLE_APPLICATION_CREDENTIALS_JSON for tofu subprocess

from tools.cloud_shared.logging import logger
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.gcp.scope_shared.core.terra_runner import get_terra_env
from tools.cloud_shared.verify.verify_summary import VerifyRow, print_verify_summary
from tools.cloud_shared.verify.verify_llm_client import verify_llm_client
from tools.cloud_shared.verify.verify_csv import get_total_rec_from_csv
from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints
print("verify_all_deploy: imports done, entering main()", flush=True)


def get_tofu_output(stack_dir: str, env: str) -> dict:
    """Retrieve output from Tofu (assumed already applied). GCP-specific: init_stack, get_terra_env."""
    from tools.gcp.scope_shared.core.terra_init import init_stack

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


def main():
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

    total_rec = get_total_rec_from_csv()

    verify_start = time.time()
    logger.operation_start("Verify", args.scope, args.env, region)
    logger.step(f"Full Verification Interface (env: {args.env}, region: {region}, total_rec from CSV: {total_rec})")

    scopes_to_verify = ["nonkube", "kube"] if args.scope == "all" else [args.scope]
    verify_phases = [f"Endpoints ({s})" for s in scopes_to_verify] + ["LLM client"]
    total_phases = len(verify_phases)
    all_rows: list[VerifyRow] = []
    phase_idx = 0

    for scope in scopes_to_verify:
        phase_idx += 1
        phase_start_time = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])

        base_url = None
        if scope == "nonkube":
            logger.info("Fetching nonkube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/gcp/nonkube", args.env)
            base_url = stack_out.get("cloud_run_url", {}).get("value") or stack_out.get("service_url", {}).get("value")
        elif scope == "kube":
            logger.info("Fetching kube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/gcp/kube", args.env)
            base_url = stack_out.get("kube_base_url", {}).get("value")
            if not base_url:
                cdn_ip = stack_out.get("cloudfront_domain_name", {}).get("value")
                base_url = f"http://{cdn_ip}" if cdn_ip else None

        if base_url:
            base_url = base_url if base_url.startswith("http") else f"https://{base_url}"
            ok, rows = verify_api_endpoints(base_url, total_rec, scope, provider="gcp")
            all_rows.extend(rows)
            if not ok:
                logger.error(f"[VERIFICATION FAILED] API endpoints are not responding correctly ({scope})")
                print_verify_summary(all_rows, args.env, total_rec)
                logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                sys.exit(1)
        else:
            skip_note = "No base URL (stack not deployed or no frontend/LB). Skipping endpoints."
            logger.info(skip_note)
            all_rows.append(VerifyRow(provider="gcp", scope=scope, endpoint="Endpoints", ok=True, notes=skip_note))

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
        print_verify_summary(all_rows, args.env, total_rec)
        logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
        sys.exit(1)

    print_verify_summary(all_rows, args.env, total_rec)

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
