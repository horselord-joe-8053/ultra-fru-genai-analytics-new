"""
Shared logic for verify_all_deploy. Used by AWS and GCP provider wrappers.

Extracts base_url from tofu outputs per scope, runs verify_api_endpoints and verify_llm_client.
Provider-specific: get_tofu_output, base_url extraction, optional kube fallback.
"""
from __future__ import annotations

import sys
import time
from typing import Callable

from tools.cloud_shared.logging import logger
from tools.cloud_shared.verify.verify_summary import VerifyRow, print_verify_summary
from tools.cloud_shared.verify.verify_llm_client import verify_llm_client
from tools.cloud_shared.verify.verify_csv import get_total_rec_from_csv
from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints


def run_verify_all_deploy(
    provider: str,
    env: str,
    region: str,
    scope: str,
    get_tofu_output_fn: Callable[[str, str], dict],
    extract_base_url: Callable[[str, dict], str | None],
    kube_fallback_fn: Callable[[str, str], str | None] | None = None,
    setup_fn: Callable[[], None] | None = None,
) -> None:
    """
    Run full deploy verification: endpoints (nonkube/kube) + LLM client.

    Args:
        provider: "aws" or "gcp" (for VerifyRow)
        env: FRU_ENV
        region: CLOUD_REGION
        scope: "nonkube", "kube", or "all"
        get_tofu_output_fn: (stack_dir, env) -> dict of tofu outputs
        extract_base_url: (scope, stack_out) -> base_url or None
        kube_fallback_fn: Optional (env, region) -> base_url for kube when tofu outputs lack URL (e.g. AWS EKS LB)
        setup_fn: Optional pre-setup (e.g. get_base_vars, load_gcp_env)
    """
    if setup_fn:
        setup_fn()

    total_rec = get_total_rec_from_csv()
    scopes_to_verify = ["nonkube", "kube"] if scope == "all" else [scope]
    verify_phases = [f"Endpoints ({s})" for s in scopes_to_verify] + ["LLM client"]
    total_phases = len(verify_phases)
    all_rows: list[VerifyRow] = []
    phase_idx = 0
    verify_start = time.time()

    logger.operation_start("Verify", scope, env, region)
    logger.step(f"Full Verification Interface (env: {env}, region: {region}, total_rec from CSV: {total_rec})")

    for s in scopes_to_verify:
        phase_idx += 1
        phase_start_time = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])

        stack_dir = _stack_dir_for_scope(provider, s)
        logger.info(f"Fetching {s} tofu outputs (tofu init + output, ~30-60s)...")
        sys.stdout.flush()
        stack_out = get_tofu_output_fn(stack_dir, env)
        base_url = extract_base_url(s, stack_out)

        if not base_url and s == "kube" and kube_fallback_fn:
            base_url = kube_fallback_fn(env, region)

        if base_url:
            if not base_url.startswith("http"):
                base_url = f"https://{base_url}"
            ok, rows = verify_api_endpoints(base_url, total_rec, scope=s, provider=provider)
            all_rows.extend(rows)
            if not ok:
                logger.error(f"[VERIFICATION FAILED] API endpoints are not responding correctly ({s})")
                print_verify_summary(all_rows, env, total_rec)
                logger.operation_end("Verify", scope, env, region, int(time.time() - verify_start), ok=False)
                sys.exit(1)
        else:
            if provider == "aws" and s == "nonkube":
                logger.error("Could not find CloudFront domain or ALB DNS in terraform outputs (nonkube).")
                logger.operation_end("Verify", scope, env, region, int(time.time() - verify_start), ok=False)
                sys.exit(1)
            skip_note = "No base URL (stack not deployed or no frontend/LB). Skipping endpoints."
            logger.info(skip_note)
            all_rows.append(VerifyRow(provider=provider, scope=s, endpoint="Endpoints", ok=True, notes=skip_note))

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
        logger.operation_end("Verify", scope, env, region, int(time.time() - verify_start), ok=False)
        sys.exit(1)

    print_verify_summary(all_rows, env, total_rec)
    verify_dur = int(time.time() - verify_start)
    logger.operation_end("Verify", scope, env, region, verify_dur, ok=True)
    logger.success("FULL VERIFICATION: SUCCESS")
    sys.exit(0)


def _stack_dir_for_scope(provider: str, scope: str) -> str:
    """Return tofu stack directory for provider and scope."""
    return f"infra_terraform/live_deploy/{provider}/{scope}"
