#!/usr/bin/env python3
"""
Remove stale module.ecs resources from kube state.

The kube stack does NOT have an ECS module; module.ecs belongs to nonkube.
If kube state was corrupted (e.g. mixed state from wrong region), these cause:
  Error: reading ELBv2 Load Balancer (arn:...us-east-2...): not a valid load balancer ARN

Run from project root with .env loaded:
  PYTHONPATH=. python tools/aws/standalone/temp_one_off/fix_kube_state_remove_stale_ecs.py --region us-east-1
"""
import argparse
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_runner import get_terra_env

load_dotenv()

STALE_ECS_STATE_ADDRESSES = [
    "module.ecs.aws_lb.main",
    "module.ecs.aws_security_group_rule.tasks_from_alb",
    "module.ecs.data.aws_region.current",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=os.getenv("CLOUD_REGION", "us-east-1"))
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    args = ap.parse_args()
    os.environ["CLOUD_REGION"] = args.region

    stack_dir = "infra_terraform/live_deploy/aws/kube"
    init_stack(stack_dir, args.env, args.region)
    env = get_terra_env(args.region)
    env["CLOUD_REGION"] = args.region

    removed = 0
    for addr in STALE_ECS_STATE_ADDRESSES:
        r = subprocess.run(
            ["tofu", "state", "rm", addr],
            cwd=stack_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        if r.returncode == 0:
            print(f"Removed: {addr}")
            removed += 1
        else:
            err = (r.stderr or r.stdout or "").strip()
            if (
                "Resource not found" in err
                or "not in state" in err.lower()
                or "No matching objects found" in err
            ):
                print(f"Skip (not in state): {addr}")
            else:
                print(f"Failed {addr}: {err[:300]}", file=sys.stderr)

    print(f"\nDone. Removed {removed} stale resource(s). Re-run deploy when ready.")


if __name__ == "__main__":
    main()
