#!/usr/bin/env python3
"""
Configure kubectl for the target cluster (AWS EKS, GCP GKE, or local).

Usage:
  python tools/standalone/kubeconfig.py --provider aws --env dev --region us-east-1
  python tools/standalone/kubeconfig.py --provider gcp --env dev --region us-central1
  python tools/standalone/kubeconfig.py --provider local --env dev

Dispatches to provider-specific scripts:
  aws  -> tools/aws/kube/eks_kubeconfig.py
  gcp  -> tools/gcp/kube/gke_kubeconfig.py
  local -> use docker-desktop context (Docker Desktop Kubernetes)
"""
import argparse
import os
import subprocess
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from tools.cloud_shared.env import load_dotenv

load_dotenv()


def _run_local(env: str, region: str | None) -> None:
    """Use Docker Desktop (or kind/minikube) context. Region is ignored for local."""
    out = subprocess.run(
        ["kubectl", "config", "get-contexts", "-o", "name"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    contexts = (out.stdout or "").strip().splitlines() if out.returncode == 0 else []
    # Prefer docker-desktop, then kind-*, then minikube
    for name in ("docker-desktop", "docker-edge"):
        if name in contexts:
            print(f"+ kubectl config use-context {name}")
            subprocess.run(["kubectl", "config", "use-context", name], check=True, timeout=10)
            return
    for ctx in contexts:
        if ctx.startswith("kind-") or ctx == "minikube":
            print(f"+ kubectl config use-context {ctx}")
            subprocess.run(["kubectl", "config", "use-context", ctx], check=True, timeout=10)
            return
    if contexts:
        print(f"Warning: No docker/kind/minikube context. Using first: {contexts[0]}")
        subprocess.run(["kubectl", "config", "use-context", contexts[0]], check=True, timeout=10)
    else:
        print("Error: No kubectl context. Enable Kubernetes in Docker Desktop or create a cluster.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Configure kubectl for target cluster")
    ap.add_argument("--provider", choices=["local", "aws", "gcp"], required=True)
    ap.add_argument("--region", default=None, help="Region (e.g. us-east-1, us-central1)")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"), help="Environment (dev, staging, prod, etc.)")
    args = ap.parse_args()

    if args.provider == "local":
        _run_local(args.env, args.region)
        return

    if args.provider == "aws":
        if not args.region:
            args.region = os.getenv("CLOUD_REGION", "us-east-1")
        os.environ["CLOUD_REGION"] = args.region
        script = os.path.join(_repo_root, "tools", "aws", "kube", "eks_kubeconfig.py")
        cmd = [sys.executable, script, "--env", args.env, "--region", args.region]
    elif args.provider == "gcp":
        if not args.region:
            args.region = os.getenv("CLOUD_REGION", os.getenv("GCP_REGION", "us-central1"))
        os.environ["CLOUD_REGION"] = args.region
        script = os.path.join(_repo_root, "tools", "gcp", "kube", "gke_kubeconfig.py")
        cmd = [sys.executable, script, "--env", args.env, "--region", args.region]
    else:
        sys.exit(1)

    pypath = _repo_root + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    env = {**os.environ, "PYTHONPATH": pypath}
    subprocess.run(cmd, cwd=_repo_root, env=env, check=True, timeout=60)


if __name__ == "__main__":
    main()
