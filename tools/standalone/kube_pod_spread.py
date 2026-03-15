#!/usr/bin/env python3
"""
Show pod/workload spread across nodes for fru-kube namespace.

Configures kubectl for the target cluster, then runs:
  kubectl get pods -n fru-kube -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,APP:.metadata.labels.app

Usage:
  python tools/standalone/kube_pod_spread.py --provider aws --env dev --region us-east-1
  python tools/standalone/kube_pod_spread.py --provider gcp --env dev --region us-central1
  python tools/standalone/kube_pod_spread.py --provider local --env dev
"""
import argparse
import os
import subprocess
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.deploy.k8s_deploy_helpers import K8S_NAMESPACE

load_dotenv()


def main() -> None:
    ap = argparse.ArgumentParser(description="Show pod spread across nodes in fru-kube")
    ap.add_argument("--provider", choices=["local", "aws", "gcp"], required=True)
    ap.add_argument("--region", default=None, help="Region (e.g. us-east-1, us-central1)")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"), help="Environment (dev, staging, prod, etc.)")
    ap.add_argument("--quiet", action="store_true", help="Skip kubeconfig output; only print pod table")
    args = ap.parse_args()

    # 1. Configure kubectl for target cluster
    kubeconfig_script = os.path.join(_repo_root, "tools", "standalone", "kubeconfig.py")
    kubeconfig_cmd = [
        sys.executable, kubeconfig_script,
        "--provider", args.provider,
        "--env", args.env,
    ]
    if args.region:
        kubeconfig_cmd += ["--region", args.region]

    pypath = _repo_root + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    env = {**os.environ, "PYTHONPATH": pypath}
    if args.quiet:
        subprocess.run(kubeconfig_cmd, cwd=_repo_root, env=env, capture_output=True, check=True, timeout=60)
    else:
        subprocess.run(kubeconfig_cmd, cwd=_repo_root, env=env, check=True, timeout=60)

    # 2. Get pod spread
    kubectl_cmd = [
        "kubectl", "get", "pods", "-n", K8S_NAMESPACE,
        "-o", "custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,APP:.metadata.labels.app",
    ]
    if args.quiet:
        result = subprocess.run(kubectl_cmd, capture_output=True, text=True, timeout=15)
        print(result.stdout or result.stderr or "")
        sys.exit(result.returncode)
    subprocess.run(kubectl_cmd, check=True, timeout=15)


if __name__ == "__main__":
    main()
