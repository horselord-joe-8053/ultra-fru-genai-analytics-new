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
- CloudFront: if OAC destroy fails (in use), waits TEARDOWN_OAC_WAIT_SEC and retries.
"""
import argparse
import os
import shlex
import subprocess
import threading
import time
from tools._env import load_dotenv, get_int_env
from tools.tofu_runner import tofu, get_tofu_env

load_dotenv()

# Configurable via .env
TEARDOWN_OAC_WAIT_SEC = get_int_env("TEARDOWN_OAC_WAIT_SEC", 900)  # CloudFront deletion can take ~15 min
VERIFY_HEARTBEAT_INTERVAL_SEC = get_int_env("VERIFY_HEARTBEAT_INTERVAL_SEC", 30)
CLOUDFRONT_OAC_IN_USE = "OriginAccessControlInUse"  # AWS error string
from tools.aws._backend import backend_config
from tools.aws._aws_vars import get_base_vars
from tools.aws.bootstrap_helpers import k8s_remove_bootstrap_and_scheduler

ORDER = {
    "kube": ["deploy-aws/kube"],
    "nonkube": ["deploy-aws/nonkube"],
    "all": ["deploy-aws/nonkube", "deploy-aws/kube", "deploy-aws/shared/nondurable"],
}


def sleep_with_heartbeat(seconds: int, message: str):
    """Sleep with periodic heartbeat. Long waits (e.g. CloudFront OAC retry) would otherwise appear hung."""
    start = time.time()
    last_heartbeat = 0
    while (time.time() - start) < seconds:
        elapsed = int(time.time() - start)
        if elapsed - last_heartbeat >= VERIFY_HEARTBEAT_INTERVAL_SEC and elapsed > 0:
            print(f"[heartbeat] {message} (elapsed: {elapsed}s)")
            last_heartbeat = elapsed
        time.sleep(1)


def run_with_heartbeat(cmd: list, cwd: str, env: dict, description: str) -> subprocess.CompletedProcess:
    """Run command with heartbeat. We use capture_output=True to inspect stderr for OAC errors, which hides
    progress; heartbeat thread provides feedback during long init/destroy runs."""
    print(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    elapsed_ref = [0]
    stop = threading.Event()

    def heartbeat():
        while not stop.is_set():
            if stop.wait(1):
                return
            elapsed_ref[0] += 1
            if elapsed_ref[0] % VERIFY_HEARTBEAT_INTERVAL_SEC == 0 and elapsed_ref[0] > 0:
                print(f"[heartbeat] {description} (elapsed: {elapsed_ref[0]}s)")

    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    finally:
        stop.set()
        t.join(timeout=2)


def pre_destroy_kube(env: str):
    """Remove CronJob and Job before kube destroy. K8s workloads block Terraform destroy."""
    try:
        k8s_remove_bootstrap_and_scheduler(env)
        print("Pre-destroy: removed kube CronJob and Job.")
    except Exception as e:
        print(f"Pre-destroy warning (kube): {e}")

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
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args)

def destroy_stack(stack_dir: str, env: str):
    """Init + destroy. On CloudFront OAC error, waits and retries (distribution deletion is async)."""
    init_stack(stack_dir, env)
    base = get_base_vars(env)

    extra = []
    if "kube" in stack_dir and "nonkube" not in stack_dir:
        cluster_name = os.getenv("EKS_CLUSTER_NAME")
        if cluster_name:
            extra += ["-var", f"eks_cluster_name={cluster_name}"]

    cmd = [os.getenv("FRU_TF_BIN", "tofu"), "destroy", "-lock=false", "-auto-approve"] + base + extra
    description = f"tofu destroy in {stack_dir}"
    result = run_with_heartbeat(cmd, cwd=stack_dir, env=get_tofu_env(), description=description)

    if result.returncode != 0:
        if CLOUDFRONT_OAC_IN_USE in result.stderr:
            print(f"CloudFront OAC still in use; waiting {TEARDOWN_OAC_WAIT_SEC}s for distribution to finish deleting...")
            sleep_with_heartbeat(
                TEARDOWN_OAC_WAIT_SEC,
                "Waiting for CloudFront distribution to finish deleting before retry",
            )
            retry_result = run_with_heartbeat(cmd, cwd=stack_dir, env=get_tofu_env(), description=description)
            if retry_result.returncode != 0:
                print(retry_result.stderr)
                raise subprocess.CalledProcessError(retry_result.returncode, retry_result.args)
        else:
            print(result.stderr)
            raise subprocess.CalledProcessError(result.returncode, result.args)

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

    # Pre-destroy: remove kube bootstrap + scheduler before Terraform destroy
    if args.scope in ("kube", "all"):
        pre_destroy_kube(args.env)

    for s in ORDER[args.scope]:
        destroy_stack(s, args.env)

    print("Done. (Shared durable remains.)")

if __name__ == "__main__":
    main()
