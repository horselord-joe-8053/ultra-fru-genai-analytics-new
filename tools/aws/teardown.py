
"""
AWS Teardown Orchestrator

Usage:
  python tools/aws/teardown.py --scope kube --env dev --non-interactive
  python tools/aws/teardown.py --scope nonkube --env dev --non-interactive
  python tools/aws/teardown.py --scope all --env dev --non-interactive

Rules:
- Never destroys deploy-aws/shared/durable.
- `all` destroys: nonkube -> kube -> shared-nondurable.
"""
import argparse, os
from tools._env import load_dotenv
from tools.tofu_runner import tofu
from tools.aws._backend import backend_config
from tools.aws._aws_vars import get_base_vars

load_dotenv()

ORDER = {
  "kube": ["deploy-aws/kube"],
  "nonkube": ["deploy-aws/nonkube"],
  "all": ["deploy-aws/nonkube","deploy-aws/kube","deploy-aws/shared/nondurable"],
}

def init_stack(stack_dir: str, env: str):
    cfg = backend_config(stack_dir, env)
    args = ["init","-upgrade"]
    for c in cfg:
        args += ["-backend-config", c]
    tofu(args, cwd=stack_dir, check=True)

def destroy_stack(stack_dir: str, env: str):
    init_stack(stack_dir, env)
    base = get_base_vars(env)
    
    # Kube-specific overrides if not in .env (though base covers it if set)
    extra = []
    if "kube" in stack_dir and "nonkube" not in stack_dir:
        cluster_name = os.getenv("EKS_CLUSTER_NAME")
        if cluster_name:
            extra += ["-var", f"eks_cluster_name={cluster_name}"]

    tofu(["destroy", "-auto-approve"] + base + extra, cwd=stack_dir, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube","nonkube","all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    args = ap.parse_args()

    token = f"{args.scope}-{args.env}-destroy"
    
    if not args.non_interactive:
        resp = input(f"Type '{token}' to confirm: ").strip()
        if resp != token:
            raise SystemExit("Confirmation failed. Exiting.")

    for s in ORDER[args.scope]:
        destroy_stack(s, args.env)

    print("Done. (Shared durable remains.)")

if __name__ == "__main__":
    main()
