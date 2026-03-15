#!/usr/bin/env python3
"""
Invalidate /analytics on kube CloudFront to clear cached HTML.

Run when Batch Analytics shows "Backend API not reachable" but /query works.
War Story 42: CloudFront edge cache can serve S3 index.html for /analytics
when API origin was not yet wired or cache was populated before wiring.

Usage:
  PYTHONPATH=. python tools/aws/standalone/invalidate_kube_analytics.py --region us-east-1
  PYTHONPATH=. python tools/aws/standalone/invalidate_kube_analytics.py --region us-east-2
"""
import argparse
import os
import subprocess
import sys

# Ensure repo root in path
_repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _repo not in sys.path:
    sys.path.insert(0, _repo)

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.deploy.deploy_common import tofu_output_json
from tools.cloud_shared.logging import logger

load_dotenv()


def main():
    ap = argparse.ArgumentParser(description="Invalidate /analytics on kube CloudFront")
    ap.add_argument("--region", default=os.getenv("CLOUD_REGION", "us-east-1"))
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    args = ap.parse_args()

    region = args.region
    env = args.env
    os.environ["CLOUD_REGION"] = region

    kube_stack = "infra_terraform/live_deploy/aws/kube"
    init_stack(kube_stack, env, region)

    out = tofu_output_json(kube_stack, env, region)
    cf_dist_id = out.get("cloudfront_distribution_id", {}).get("value")
    if not cf_dist_id:
        logger.error("cloudfront_distribution_id not found in kube stack output")
        sys.exit(1)

    logger.info(f"Invalidating /analytics on distribution {cf_dist_id} (region={region})")
    result = subprocess.run(
        [
            "aws", "cloudfront", "create-invalidation",
            "--distribution-id", cf_dist_id,
            "--paths", "/analytics", "/analytics/*",
        ],
        env={**os.environ, "CLOUD_REGION": region},
        timeout=60,
    )
    if result.returncode != 0:
        logger.error("create-invalidation failed")
        sys.exit(result.returncode)

    logger.success("Invalidation created. Wait 1-2 min for edges to update, then retry Batch Analytics.")


if __name__ == "__main__":
    main()
