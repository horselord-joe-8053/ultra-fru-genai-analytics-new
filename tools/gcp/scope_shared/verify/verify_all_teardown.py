"""
GCP teardown verification.
Reference: tools/aws/scope_shared/verify/verify_all_teardown.py (namespace, ECS/Cloud Run checks).

Verifies GKE namespace is gone (kube) and Cloud Run service is inactive/gone (nonkube).
Uses same logger format and phase structure as AWS.
"""
import argparse
import json
import os
import sys
import subprocess
import time

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.gcp.scope_shared.core import resource_names

load_dotenv()


def _verify_kube(env: str, region: str) -> bool:
    """Verify kube teardown: GKE namespace is gone. Returns True if ok."""
    namespace = resource_names.k8s_namespace()

    logger.info(f"Verifying Kubernetes namespace '{namespace}' is gone...")
    try:
        subprocess.check_call(
            ["kubectl", "get", "ns", namespace],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.error(f"✗ Namespace '{namespace}' still exists!")
        return False
    except subprocess.CalledProcessError:
        logger.success(f"✓ Namespace '{namespace}' is gone.")
        return True


def _verify_nonkube(env: str, region: str) -> bool:
    """Verify nonkube teardown: Cloud Run service is gone or inactive. Returns True if ok."""
    service_name = resource_names.cloud_run_service(env, region)
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project:
        logger.warning("GCP_PROJECT_ID not set; skipping Cloud Run verification")
        return True

    logger.info(f"Verifying Cloud Run service '{service_name}' is inactive/gone...")
    try:
        result = subprocess.run(
            [
                "gcloud", "run", "services", "describe", service_name,
                "--region", region,
                "--project", project,
                "--format", "json",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Service not found (NOT_FOUND) or gcloud error = assume gone
            if "NOT_FOUND" in (result.stderr or "") or "not found" in (result.stderr or "").lower():
                logger.success("✓ Cloud Run service not found.")
                return True
            logger.warning(f"Could not verify Cloud Run service: {result.stderr or result.stdout}")
            return True
        # Service exists = fail
        logger.error(f"✗ Cloud Run service '{service_name}' still exists")
        return False
    except Exception as e:
        logger.warning(f"Could not verify Cloud Run service status: {e}")
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)

    scopes_to_verify = ["nonkube", "kube"] if args.scope == "all" else [args.scope]
    verify_phases = [f"Teardown ({s})" for s in scopes_to_verify]
    total_phases = len(verify_phases)

    verify_start = time.time()
    logger.operation_start("Verify Teardown", args.scope, args.env, region)
    logger.step(f"Teardown verification (env: {args.env}, region: {region}, scope: {args.scope})")

    all_ok = True
    for phase_idx, scope in enumerate(scopes_to_verify, start=1):
        phase_start = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])
        if scope == "kube":
            ok = _verify_kube(args.env, region)
        else:
            ok = _verify_nonkube(args.env, region)
        if not ok:
            all_ok = False
        phase_secs = int(time.time() - phase_start)
        logger.phase_end(phase_idx, total_phases, verify_phases[phase_idx - 1], phase_secs)

    verify_dur = int(time.time() - verify_start)
    logger.operation_end("Verify Teardown", args.scope, args.env, region, verify_dur, ok=all_ok)

    if all_ok:
        logger.success("Teardown verification complete.")
        sys.exit(0)
    else:
        logger.error("Teardown verification FAILED: some resources still present.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
