#!/usr/bin/env python3
"""
Minimal test: tofu plan on nonkube stack for us-east-2.

Narrowest scope that touches CloudFront:
- CloudFront API is us-east-1 only; provider is configured with region=us-east-2
- Plan makes API calls (including CloudFront) to validate state
- No actual changes; fast (~1–2 min if shared stacks exist)

Use this to verify auth + CloudFront region behavior before a full deploy.

Usage (from repo root):
  PYTHONPATH=. python tools/aws/standalone/test_cloudfront_plan_us_east_2.py

Requires: shared durable + nondurable stacks must exist in us-east-2
(otherwise plan fails on remote state).
"""
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.core.terra_runner import terra_capture

load_dotenv()

STACK_DIR = "infra_terraform/live_deploy/aws/nonkube"
REGION = "us-east-2"
ENV = os.getenv("FRU_ENV", "dev")


def main() -> int:
    logger.step(f"Minimal CloudFront test: tofu plan on nonkube for {REGION}")
    logger.info(f"  Stack: {STACK_DIR}")
    logger.info(f"  Env: {ENV}")
    logger.info("  (Provider region=us-east-2; CloudFront API is us-east-1)")
    logger.info("")

    os.environ["CLOUD_REGION"] = REGION
    init_stack(STACK_DIR, ENV, REGION)
    get_base_vars(ENV, REGION)

    result = terra_capture(["plan", "-detailed-exitcode"], cwd=STACK_DIR, region=REGION)
    # exitcode 0 = no changes, 2 = changes planned (both OK)
    if result.returncode in (0, 2):
        logger.success("Plan OK (auth + CloudFront API calls succeeded)")
        return 0
    logger.error(f"Plan failed (exit {result.returncode})")
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
