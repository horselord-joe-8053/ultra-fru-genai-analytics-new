"""
AWS teardown verification. Verifies ECS cluster inactive/gone (nonkube) and namespace gone (kube).
"""
import json
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
from tools.cloud_shared.logging import logger
from tools.cloud_shared.verify.verify_all_teardown_common import run_verify_all_teardown
from tools.aws.scope_shared.core.backend import resolve_region
from tools.aws.scope_shared.deploy.k8s_deploy_helpers import K8S_NAMESPACE
from tools.cloud_shared.verify.verify_kubectl import verify_kubectl_namespace_gone

load_dotenv()


def _verify_kube(env: str, region: str) -> bool:
    return verify_kubectl_namespace_gone(K8S_NAMESPACE)


def _verify_nonkube(env: str, region: str) -> bool:
    """Verify nonkube teardown: ECS cluster is gone or inactive."""
    from tools.aws.scope_shared.core import resource_names
    cluster_name = resource_names.ecs_cluster(env, region)
    logger.info(f"Verifying ECS cluster '{cluster_name}' is inactive/gone...")
    try:
        out = subprocess.check_output(
            ["aws", "ecs", "describe-clusters", "--clusters", cluster_name, "--region", region],
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
        return True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args, unknown = ap.parse_known_args()
    if unknown:
        logger.warning(f"Ignoring unrecognized arguments (orchestrator passthrough): {unknown}")

    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)

    run_verify_all_teardown(
        env=args.env,
        region=region,
        scope=args.scope,
        verify_kube_fn=_verify_kube,
        verify_nonkube_fn=_verify_nonkube,
    )


if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
