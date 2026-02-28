"""
Explicitly destroy shared durable stack.

Usage:
  ALLOW_DURABLE_DESTROY=YES python tools/aws/standalone/destroy_durable.py --env dev --force
"""
import argparse
import json
import os

from tools.cloud_shared.env import load_dotenv, require
from tools.aws.scope_shared.core.terra_runner import terra
from tools.aws.scope_shared.core.backend import backend_config, resolve_region
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.provider_config_handler import get_azs, get_subnet_cidrs

load_dotenv()


def init_stack(env, region):
    cfg = backend_config("infra_terraform/live_deploy/aws/scope_shared/durable", env, region=region, cloud="aws")
    args = ["init", "-upgrade"]
    for c in cfg:
        args += ["-backend-config", c]
    terra(args, cwd="infra_terraform/live_deploy/aws/scope_shared/durable")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    args = ap.parse_args()

    region = args.region or resolve_region(None)
    token = f"durable-{args.env}-destroy"

    if not args.non_interactive:
        resp = input(f"Type '{token}' to confirm durable destroy: ").strip()
        if resp != token:
            raise SystemExit("Confirmation failed.")

    init_stack(args.env, region)
    get_base_vars(args.env, region)

    azs = get_azs(region)
    public_cidrs, private_cidrs = get_subnet_cidrs(region)

    terra([
        "destroy", "-auto-approve",
        "-var", "allow_destroy_durable=true",
        "-var", f"vpc_cidr={require('VPC_CIDR')}",
        "-var", f"azs={json.dumps(azs)}",
        "-var", f"public_subnet_cidrs={json.dumps(public_cidrs)}",
        "-var", f"private_subnet_cidrs={json.dumps(private_cidrs)}",
    ], cwd="infra_terraform/live_deploy/aws/scope_shared/durable", check=True)

if __name__ == "__main__":
    main()
