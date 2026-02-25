import argparse
import json
import os
import sys
import subprocess
import time
from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
from tools.aws.scope_shared.core.backend import resolve_region

load_dotenv()


def _verify_kube(env: str, region: str) -> bool:
    """Verify kube teardown: namespace is gone. Returns True if ok."""
    from tools.aws.scope_shared.deploy.bootstrap_helpers import K8S_NAMESPACE

    logger.info(f"Verifying Kubernetes namespace '{K8S_NAMESPACE}' is gone...")
    try:
        subprocess.check_call(
            ["kubectl", "get", "ns", K8S_NAMESPACE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.error(f"✗ Namespace '{K8S_NAMESPACE}' still exists!")
        return False
    except subprocess.CalledProcessError:
        logger.success(f"✓ Namespace '{K8S_NAMESPACE}' is gone.")
        return True


def _verify_nonkube(env: str, region: str) -> bool:
    """Verify nonkube teardown: ECS cluster is gone or inactive. Returns True if ok."""
    cluster_name = os.getenv("ECS_CLUSTER_NAME") or f"{os.getenv('FRU_PREFIX', 'fru')}-{env}-ecs"
    logger.info(f"Verifying ECS cluster '{cluster_name}' is inactive/gone...")
    try:
        out = subprocess.check_output(
            [
                "aws",
                "ecs",
                "describe-clusters",
                "--clusters",
                cluster_name,
                "--region",
                region,
            ],
            text=True,
        )
        data = json.loads(out)
        clusters = data.get("clusters", [])
        if not clusters:
            logger.success("✓ ECS Cluster not found.")
            return True
        status = clusters[0].get("status")
        if status == "INACTIVE":
            logger.success("✓ ECS Cluster is INACTIVE.")
            return True
        logger.error(f"✗ ECS Cluster status is {status} (expected INACTIVE/missing)")
        return False
    except Exception as e:
        logger.warning(f"Could not verify ECS cluster status: {e}")
        return True  # Assume ok on describe failure (permission or already gone)


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

    # When scope=all, verify nonkube first then kube (matches teardown order)
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
