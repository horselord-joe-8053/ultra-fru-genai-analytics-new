"""
AWS Teardown Orchestrator

Usage:
  python tools/aws/teardown.py --scope kube --env dev --non-interactive
  python tools/aws/teardown.py --scope nonkube --env dev --non-interactive
  python tools/aws/teardown.py --scope all --env dev --non-interactive

Rules:
- Never destroys deploy-aws/shared/durable.
- `all` destroys: nonkube -> kube -> shared-nondurable.
- Before destroying kube: removes CronJob + Job (scheduler + bootstrap).
- Retry logic: configurable via config/retry_config.json (retriable/non-retriable patterns).
"""
import argparse
import os
import subprocess

from tools import logger
from tools._env import load_dotenv
from tools.aws._backend import backend_config
from tools.aws._aws_vars import get_base_vars
from tools.aws.bootstrap_helpers import k8s_remove_bootstrap_and_scheduler
from tools.subprocess_retry import run_with_retry
from tools.tofu_runner import get_tofu_env
from tools.with_heartbeat import run_with_heartbeat

load_dotenv()

ORDER = {
    "kube": ["deploy-aws/kube"],
    "nonkube": ["deploy-aws/nonkube"],
    "all": ["deploy-aws/nonkube", "deploy-aws/kube", "deploy-aws/shared/nondurable"],
}


def pre_destroy_kube(env: str):
    """Remove CronJob and Job before kube destroy. K8s workloads block Terraform destroy."""
    try:
        k8s_remove_bootstrap_and_scheduler(env)
        logger.info("Pre-destroy: removed kube CronJob and Job.")
    except Exception as e:
        logger.warning(f"Pre-destroy warning (kube): {e}")


def init_stack(stack_dir: str, env: str):
    """Init with backend config for this stack. Each stack has its own S3 state key."""
    cfg = backend_config(stack_dir, env)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    init_cmd = [exe] + args
    description = f"tofu init -upgrade -reconfigure in {stack_dir}"
    result = run_with_heartbeat(init_cmd, cwd=stack_dir, env=get_tofu_env(), description=description)
    if result.returncode != 0:
        if result.stderr:
            logger.error(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args)


def destroy_stack(stack_dir: str, env: str):
    """Init + destroy. Retry on configurable retriable errors (config/retry_config.json)."""
    init_stack(stack_dir, env)
    base = get_base_vars(env)

    extra = []
    if "kube" in stack_dir and "nonkube" not in stack_dir:
        cluster_name = os.getenv("EKS_CLUSTER_NAME")
        if cluster_name:
            extra += ["-var", f"eks_cluster_name={cluster_name}"]

    cmd = [os.getenv("FRU_TF_BIN", "tofu"), "destroy", "-lock=false", "-auto-approve"] + base + extra
    description = f"tofu destroy in {stack_dir}"
    run_with_retry(
        cmd,
        cwd=stack_dir,
        env=get_tofu_env(),
        description=description,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    args = ap.parse_args()

    token = f"{args.scope}-{args.env}-destroy"

    if not args.non_interactive:
        resp = input(f"Type '{token}' to confirm: ").strip()
        if resp != token:
            raise SystemExit("Confirmation failed. Exiting.")

    if args.scope in ("kube", "all"):
        pre_destroy_kube(args.env)

    for s in ORDER[args.scope]:
        destroy_stack(s, args.env)

    logger.success("Done. (Shared durable remains.)")


if __name__ == "__main__":
    main()
