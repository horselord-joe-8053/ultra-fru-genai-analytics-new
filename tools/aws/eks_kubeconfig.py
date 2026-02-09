
"""
Configure kubectl for EKS.

Usage:
  python tools/aws/eks_kubeconfig.py --env dev
"""
import argparse, os, subprocess
from tools._env import load_dotenv, require

load_dotenv()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    args = ap.parse_args()
    region = require("AWS_REGION")
    cluster = require("EKS_CLUSTER_NAME")
    print("+ aws eks update-kubeconfig")
    subprocess.run(["aws","eks","update-kubeconfig","--region",region,"--name",cluster], check=False)

if __name__ == "__main__":
    main()
