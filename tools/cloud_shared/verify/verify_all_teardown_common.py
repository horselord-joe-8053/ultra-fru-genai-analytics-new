"""
Shared logic for verify_all_teardown. Used by AWS and GCP provider wrappers.

Provider-specific: verify_kube_fn, verify_nonkube_fn (ECS vs Cloud Run).
"""
import sys
import time
from typing import Callable

from tools.cloud_shared.logging import logger


def run_verify_all_teardown(
    env: str,
    region: str,
    scope: str,
    verify_kube_fn: Callable[[str, str], bool],
    verify_nonkube_fn: Callable[[str, str], bool],
) -> None:
    """
    Run teardown verification: kube (namespace gone) and nonkube (ECS/Cloud Run gone).

    Args:
        env: FRU_ENV
        region: CLOUD_REGION
        scope: "nonkube", "kube", or "all"
        verify_kube_fn: (env, region) -> True if ok
        verify_nonkube_fn: (env, region) -> True if ok
    """
    scopes_to_verify = ["nonkube", "kube"] if scope == "all" else [scope]
    verify_phases = [f"Teardown ({s})" for s in scopes_to_verify]
    total_phases = len(verify_phases)

    verify_start = time.time()
    logger.operation_start("Verify Teardown", scope, env, region)
    logger.step(f"Teardown verification (env: {env}, region: {region}, scope: {scope})")

    all_ok = True
    for phase_idx, s in enumerate(scopes_to_verify, start=1):
        phase_start = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])
        ok = verify_kube_fn(env, region) if s == "kube" else verify_nonkube_fn(env, region)
        if not ok:
            all_ok = False
        phase_secs = int(time.time() - phase_start)
        logger.phase_end(phase_idx, total_phases, verify_phases[phase_idx - 1], phase_secs)

    verify_dur = int(time.time() - verify_start)
    logger.operation_end("Verify Teardown", scope, env, region, verify_dur, ok=all_ok)

    if all_ok:
        logger.success("Teardown verification complete.")
        sys.exit(0)
    else:
        logger.error("Teardown verification FAILED: some resources still present.")
        sys.exit(1)
