
"""
Apply Kubernetes manifests (bootstrap + schedule) to EKS.

Examples:
  python tools/aws/kube_apply.py --env dev --phase bootstrap
  python tools/aws/kube_apply.py --env dev --phase schedule

This tool:
- ensures kubeconfig for EKS
- creates namespace `fru`
- substitutes SPARK_IMAGE and DELTA_ROOT
- applies Job/CronJob manifests
"""
import argparse, os, subprocess
from tools._env import load_dotenv, require

load_dotenv()

def render(template_path, subs):
    s = open(template_path, "r").read()
    for k,v in subs.items():
        s = s.replace("${"+k+"}", v)
    return s

def kubectl(args, input_text=None):
    cmd = ["kubectl"] + args
    print("+", " ".join(cmd))
    subprocess.run(cmd, input=input_text, text=True, check=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--phase", choices=["bootstrap","schedule"], required=True)
    args = ap.parse_args()

    # ensure kubeconfig
    subprocess.run(["python","tools/aws/eks_kubeconfig.py","--env",args.env], check=False)

    spark_image = None
    # Prefer fully-qualified repo URL from state if available; fallback to env
    spark_image = f"{require('ECR_REPO_SPARK')}:{require('SPARK_IMAGE_TAG')}"
    delta_root  = f"s3a://{require('S3_DELTA_BUCKET')}/delta"

    # namespace
    kubectl(["apply","-f","-"], input_text="apiVersion: v1\nkind: Namespace\nmetadata:\n  name: fru\n")

    if args.phase == "bootstrap":
        txt = render("deploy-aws/kube/k8s/bootstrap-job.yaml", {"SPARK_IMAGE": spark_image, "DELTA_ROOT": delta_root})
        kubectl(["apply","-f","-"], input_text=txt)
    else:
        txt = render("deploy-aws/kube/k8s/spark-cronjob.yaml", {"SPARK_IMAGE": spark_image, "DELTA_ROOT": delta_root})
        kubectl(["apply","-f","-"], input_text=txt)

if __name__ == "__main__":
    main()
