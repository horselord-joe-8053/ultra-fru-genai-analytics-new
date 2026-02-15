
"""
AWS Deploy Orchestrator (Full Infra)

One-line usage:
  python tools/deploy-orchestrator-aws.py --scope kube --env dev
  python tools/deploy-orchestrator-aws.py --scope nonkube --env dev

Notes:
- This orchestrator applies stacks in a safe order.
- It does NOT destroy durable infra.
- It intentionally avoids "smart" inference. Use outputs printed at the end.
"""
import argparse, os, subprocess
from tools._env import load_dotenv, require
from tools.tofu_runner import tofu

load_dotenv()

def base_vars(env):
    return [
        "-var", f"env={env}",
        "-var", f"prefix={require('FRU_PREFIX')}",
        "-var", f"aws_region={os.getenv('CLOUD_REGION', '').strip() or require('AWS_REGION')}",
    ]

def apply_stack(stack, env, extra_vars):
    tofu(["init","-upgrade"], cwd=stack)
    tofu(["apply","-auto-approve"] + base_vars(env) + extra_vars, cwd=stack)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube","nonkube"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    args = ap.parse_args()

    # shared durable
    apply_stack("deploy-aws/shared/durable", args.env, [
        "-var", f"vpc_cidr={require('VPC_CIDR')}",
        "-var", "azs=["us-east-1a","us-east-1b"]",
        "-var", "public_subnet_cidrs=["10.0.1.0/24","10.0.2.0/24"]",
        "-var", "private_subnet_cidrs=["10.0.101.0/24","10.0.102.0/24"]",
    ])

    # shared non-durable
    apply_stack("deploy-aws/shared/nondurable", args.env, [
        "-var", f"delta_bucket={require('S3_DELTA_BUCKET')}",
        "-var", f"artifacts_bucket={require('S3_ARTIFACT_BUCKET')}",
        "-var", f"ecr_repo_app={require('ECR_REPO_APP')}",
        "-var", f"ecr_repo_spark={require('ECR_REPO_SPARK')}",
    ])

    if args.scope == "kube":
        apply_stack("deploy-aws/kube", args.env, [
            "-var", f"eks_cluster_name={require('EKS_CLUSTER_NAME')}",
            "-var", f"eks_instance_types=["{require('EKS_NODE_INSTANCE_TYPES')}"]",
            "-var", f"eks_desired_nodes={require('EKS_DESIRED_NODES')}",
            # subnet IDs should be wired via remote-state in a later iteration; for now user can pass after first apply.
            "-var", "private_subnet_ids=[]",
        ])
        print("\nKube scope applied. Next:")
        print("1) Build/push images: python tools/build_and_push_images_aws.py --scope kube")
        print("2) Apply k8s manifests: python tools/kube_apply.py --env dev --phase bootstrap|schedule")
    else:
        apply_stack("deploy-aws/nonkube", args.env, [
            "-var", f"ecs_cluster_name={require('ECS_CLUSTER_NAME')}",
            "-var", f"alb_name={require('ALB_NAME')}",
            "-var", f"app_image={require('ECR_REPO_APP')}:{require('APP_IMAGE_TAG')}",
            # VPC/subnets should be wired via remote-state in a later iteration
            "-var", "vpc_id=""",
            "-var", "public_subnet_ids=[]",
            "-var", "private_subnet_ids=[]",
        ])
        print("\nNonkube scope applied. Next:")
        print("1) Build/push images: python tools/build_and_push_images_aws.py --scope nonkube")
        print("2) Schedule Spark on ECS: python tools/ecs_spark_schedule.py --env dev --phase bootstrap|schedule")

if __name__ == "__main__":
    main()
