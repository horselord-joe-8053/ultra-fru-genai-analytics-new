"""
Install AWS Load Balancer Controller on EKS.

Required for fru-api-svc with aws-load-balancer-type: external (NLB instead of Classic ELB).

Usage:
  python tools/aws/kube/install_aws_load_balancer_controller.py [--env dev] [--region us-east-1] [--profile PROFILE]

Prerequisites: eksctl, helm, kubectl, AWS credentials, kubeconfig pointing at the cluster.
Cross-platform: Python (runs on Windows, macOS, Linux).
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.core import resource_names
from tools.aws.scope_shared.core.backend import resolve_region

load_dotenv()

IAM_POLICY_URL = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v3.0.0/docs/install/iam_policy.json"


def run(cmd: list[str], check: bool = True, capture: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    env = env or os.environ
    print("+", " ".join(cmd))
    if capture:
        return subprocess.run(cmd, env=env, capture_output=True, text=True, check=check)
    return subprocess.run(cmd, env=env, check=check)


def main():
    ap = argparse.ArgumentParser(description="Install AWS Load Balancer Controller on EKS (NLB track)")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--profile", default=os.getenv("AWS_PROFILE", ""), help="AWS profile")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    cluster_name = resource_names.eks_cluster(args.env, region)
    # Override EKS_CLUSTER_NAME so eks_kubeconfig and eksctl use correct cluster (not legacy from .env)
    env = {**os.environ, "CLOUD_REGION": region, "EKS_CLUSTER_NAME": cluster_name}
    if args.profile:
        env["AWS_PROFILE"] = args.profile

    print(f"Installing AWS Load Balancer Controller for cluster={cluster_name} region={region}")

    # Ensure kubectl context points at the cluster
    run([sys.executable, "tools/aws/kube/eks_kubeconfig.py", "--env", args.env], env=env, check=False)

    # 1. Ensure OIDC provider (eksctl adds if missing)
    try:
        run(
            ["eksctl", "utils", "associate-iam-oidc-provider", "--cluster", cluster_name, "--region", region, "--approve"],
            env=env,
        )
    except subprocess.CalledProcessError:
        print("(OIDC provider associate skipped or already exists)")

    # 2. Create IAM policy if not exists
    out = run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], env=env, capture=True)
    account_id = out.stdout.strip()
    policy_arn = f"arn:aws:iam::{account_id}:policy/AWSLoadBalancerControllerIAMPolicy"

    check = run(["aws", "iam", "get-policy", "--policy-arn", policy_arn], env=env, check=False, capture=True)
    if check.returncode != 0:
        print("Creating IAM policy AWSLoadBalancerControllerIAMPolicy...")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            try:
                with urllib.request.urlopen(IAM_POLICY_URL, timeout=30) as r:
                    f.write(r.read().decode())
                f.flush()
                run(
                    ["aws", "iam", "create-policy", "--policy-name", "AWSLoadBalancerControllerIAMPolicy", "--policy-document", f"file://{f.name}"],
                    env=env,
                )
            finally:
                os.unlink(f.name)
    print(f"Using policy: {policy_arn}")

    # 3. Create IAM role + ServiceAccount
    # eksctl bug: if SA was deleted from k8s but CF stack exists, "create" returns "no tasks".
    # Workaround: delete iamserviceaccount first if SA missing in k8s, then create.
    sa_check = run(
        ["kubectl", "get", "serviceaccount", "aws-load-balancer-controller", "-n", "kube-system"],
        env=env,
        check=False,
        capture=True,
    )
    if sa_check.returncode != 0:
        print("ServiceAccount not found in k8s; deleting stale eksctl state (if any) before create...")
        run(
            [
                "eksctl", "delete", "iamserviceaccount",
                "--cluster", cluster_name,
                "--namespace", "kube-system",
                "--name", "aws-load-balancer-controller",
                "--region", region,
            ],
            env=env,
            check=False,
        )
        print("Waiting 15s for CloudFormation stack deletion to complete...")
        time.sleep(15)
    run(
        [
            "eksctl", "create", "iamserviceaccount",
            "--cluster", cluster_name,
            "--namespace", "kube-system",
            "--name", "aws-load-balancer-controller",
            "--attach-policy-arn", policy_arn,
            "--override-existing-serviceaccounts",
            "--region", region,
            "--approve",
        ],
        env=env,
    )

    # 4. Add Helm repo and install controller
    run(["helm", "repo", "add", "eks", "https://aws.github.io/eks-charts"], env=env, check=False)
    run(["helm", "repo", "update"], env=env)

    # Get VPC ID (avoids IMDS lookup; fixes CrashLoopBackOff on IMDSv2-restricted nodes)
    vpc_id = ""
    try:
        out = run(
            ["aws", "eks", "describe-cluster", "--name", cluster_name, "--region", region, "--query", "cluster.resourcesVpcConfig.vpcId", "--output", "text"],
            env=env,
            capture=True,
        )
        vpc_id = (out.stdout or "").strip()
    except subprocess.CalledProcessError:
        pass

    helm_args = [
        "helm", "upgrade", "--install", "aws-load-balancer-controller", "eks/aws-load-balancer-controller",
        "-n", "kube-system",
        "--set", f"clusterName={cluster_name}",
        "--set", "serviceAccount.create=false",
        "--set", "serviceAccount.name=aws-load-balancer-controller",
        "--set", f"region={region}",
    ]
    if vpc_id:
        helm_args += ["--set", f"vpcId={vpc_id}"]

    run(helm_args, env=env)

    # 5. Wait for controller pods (webhook needs them before fru-api-svc apply)
    print("Waiting for controller pods (up to 5 min)...")
    result = run(
        ["kubectl", "wait", "--for=condition=available", "--timeout=300s", "deployment/aws-load-balancer-controller", "-n", "kube-system"],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        print("WARNING: Controller not ready within 5 min. kube_apply will retry api-service when webhook is up.")

    run(["kubectl", "get", "deployment", "-n", "kube-system", "aws-load-balancer-controller"], env=env)
    print("Done. The controller will reconcile fru-api-svc and create an NLB.")


if __name__ == "__main__":
    main()
    sys.exit(0)
