
"""
Explicitly destroy shared durable stack.

Usage:
  ALLOW_DURABLE_DESTROY=YES python tools/aws/standalone/destroy_durable.py --env dev --force
"""
import argparse, os
from tools.cloud_shared.env import load_dotenv, require
from tools.aws.scope_shared.core.terra_runner import terra
from tools.aws.scope_shared.core.backend import backend_config
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars

load_dotenv()

def init_stack(env):
    cfg = backend_config("live_deploy_aws/scope_shared/durable", env, region=None, cloud="aws")
    args = ["init","-upgrade"]
    for c in cfg:
        args += ["-backend-config", c]
    terra(args, cwd="live_deploy_aws/scope_shared/durable")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    args = ap.parse_args()

    token = f"durable-{args.env}-destroy"
    
    if not args.non_interactive:
        resp = input(f"Type '{token}' to confirm durable destroy: ").strip()
        if resp != token:
            raise SystemExit("Confirmation failed.")

    init_stack(args.env)
    base = get_base_vars(args.env)
    
    terra([
        "destroy", "-auto-approve",
        "-var", "allow_destroy_durable=true",
        "-var", f"vpc_cidr={require('VPC_CIDR')}",
        "-var", 'azs=["us-east-1a","us-east-1b"]',
        "-var", 'public_subnet_cidrs=["10.0.1.0/24","10.0.2.0/24"]',
        "-var", 'private_subnet_cidrs=["10.0.101.0/24","10.0.102.0/24"]',
    ] + base, cwd="live_deploy_aws/scope_shared/durable", check=True)

if __name__ == "__main__":
    main()
