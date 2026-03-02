"""
GCP Teardown Orchestrator (reference: tools/aws/teardown.py).

Usage:
  python tools/gcp/teardown.py --scope kube --env dev
  python tools/gcp/teardown.py --scope nonkube --env dev
  python tools/gcp/teardown.py --scope all --env dev --non-interactive

Order (matches AWS): scope stacks first (nonkube, kube), then nondurable, durable, durable_with_cooloff.
"""
import argparse
import os
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.stats import TeardownStats, scope_for
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.cloud_shared.logging import logger

load_dotenv()

ORDER = {
    "kube": ["infra_terraform/live_deploy/gcp/kube"],
    "nonkube": ["infra_terraform/live_deploy/gcp/nonkube"],
    "all": [
        "infra_terraform/live_deploy/gcp/nonkube",
        "infra_terraform/live_deploy/gcp/kube",
        "infra_terraform/live_deploy/gcp/scope_shared/nondurable",
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    ap.add_argument("--non-interactive", action="store_true")
    ap.add_argument("--incl-dura", action="store_true", help="Include durable (VPC) in teardown (scope=all)")
    ap.add_argument("--incl-dura-all", action="store_true", help="Include durable and durable_with_cooloff (secrets)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    stats = TeardownStats()

    stacks_to_destroy = list(ORDER[args.scope])
    if args.scope == "all" and (args.incl_dura or args.incl_dura_all):
        stacks_to_destroy.append("infra_terraform/live_deploy/gcp/scope_shared/durable")
        if args.incl_dura_all:
            stacks_to_destroy.append("infra_terraform/live_deploy/gcp/scope_shared/durable_with_cooloff")

    for stack in stacks_to_destroy:
        stack_path = os.path.join(repo_root, stack)
        if not os.path.isdir(stack_path):
            continue
        stats.set_scope(scope_for(stack))
        logger.step(f"Destroy {stack}...")
        from tools.gcp.scope_shared.core.terra_init import init_stack
        from tools.gcp.scope_shared.core.terra_runner import terra
        init_stack(stack_path, args.env, region)
        destroy_cmd = ["destroy", "-auto-approve"] if args.non_interactive else ["destroy"]
        with stats.timed("Tofu destroy", stack.split("/")[-1]):
            terra(destroy_cmd, cwd=stack_path, check=False)

    stats.print_summary()
    logger.success("Teardown complete.")


if __name__ == "__main__":
    main()
