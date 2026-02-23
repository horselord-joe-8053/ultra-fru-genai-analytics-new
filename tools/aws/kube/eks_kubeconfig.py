
"""
Configure kubectl for EKS.

Usage:
  python tools/aws/kube/eks_kubeconfig.py --env dev
"""
import argparse, os, subprocess
from tools.cloud_shared.env import load_dotenv, require

load_dotenv()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    args = ap.parse_args()
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(None)
    cluster = os.getenv("EKS_CLUSTER_NAME") or os.getenv("TF_VAR_eks_cluster_name") or f"{os.getenv('FRU_PREFIX', 'fru')}-{args.env}-eks"
    print("+ aws eks update-kubeconfig")
    subprocess.run(
        ["aws", "eks", "update-kubeconfig", "--region", region, "--name", cluster],
        check=False,
        timeout=30,
    )

if __name__ == "__main__":
    main()
