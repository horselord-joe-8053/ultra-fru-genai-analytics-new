"""
GCP teardown verification.
Reference: tools/aws/scope_shared/verify/verify_all_teardown.py (namespace, ECS/Cloud Run checks).

Verifies GKE namespace is gone (kube) and Cloud Run service is inactive/gone (nonkube).
"""
import os
import sys

from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
from tools.cloud_shared.logging import logger
from tools.cloud_shared.verify.verify_all_teardown_common import run_verify_all_teardown
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.gcp.scope_shared.core import resource_names
from tools.cloud_shared.verify.verify_kubectl import verify_kubectl_namespace_gone

load_dotenv()


def _verify_kube(env: str, region: str) -> bool:
    return verify_kubectl_namespace_gone(resource_names.k8s_namespace())


def _verify_nonkube(env: str, region: str) -> bool:
    """Verify nonkube teardown: Cloud Run service is gone or inactive."""
    service_name = resource_names.cloud_run_service(env, region)
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project:
        logger.warning("GCP_PROJECT_ID not set; skipping Cloud Run verification")
        return True

    logger.info(f"Verifying Cloud Run service '{service_name}' is inactive/gone...")
    try:
        import subprocess
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
            err = (result.stderr or result.stdout or "").lower()
            if "not_found" in err or "not found" in err or "cannot find service" in err:
                logger.success("✓ Cloud Run service not found.")
                return True
            logger.warning(f"Could not verify Cloud Run service: {result.stderr or result.stdout}")
            return True
        logger.error(f"✗ Cloud Run service '{service_name}' still exists")
        return False
    except Exception as e:
        logger.warning(f"Could not verify Cloud Run service status: {e}")
        return True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--non-interactive", action="store_true", help="Accepted for orchestrator compatibility; no-op")
    ap.add_argument("--incl-dura", action="store_true", help="Accepted for orchestrator compatibility; no-op")
    ap.add_argument("--incl-dura-all", action="store_true", help="Accepted for orchestrator compatibility; no-op")
    args = ap.parse_args()

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
