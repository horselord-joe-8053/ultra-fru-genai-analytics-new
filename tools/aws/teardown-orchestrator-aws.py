
"""
AWS Teardown Orchestrator

Usage:
  python tools/teardown-orchestrator-aws.py --scope kube --env dev --non-interactive
  python tools/teardown-orchestrator-aws.py --scope nonkube --env dev --non-interactive
  python tools/teardown-orchestrator-aws.py --scope all --env dev --non-interactive

Rules:
- Never destroys live-deploy-aws/shared/durable.
- `all` destroys: nonkube -> kube -> shared-nondurable.
"""
import argparse, os
from tools._env import load_dotenv
from tools.tofu_runner import tofu

load_dotenv()

def destroy_stack(stack):
    tofu(["init","-upgrade"], cwd=stack)
    tofu(["destroy","-auto-approve"], cwd=stack)

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

    if args.scope == "kube":
        destroy_stack("live-deploy-aws/kube")
    elif args.scope == "nonkube":
        destroy_stack("live-deploy-aws/nonkube")
    else:
        destroy_stack("live-deploy-aws/nonkube")
        destroy_stack("live-deploy-aws/kube")
        destroy_stack("live-deploy-aws/shared/nondurable")

    print("Done. (Shared durable remains.)")

if __name__ == "__main__":
    main()
