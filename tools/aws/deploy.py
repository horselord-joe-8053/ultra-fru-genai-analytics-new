
"""
AWS Deploy Orchestrator (legacy-aware, best-practice simplification)

Usage:
  python tools/aws/deploy.py --scope kube --env dev
  python tools/aws/deploy.py --scope nonkube --env dev

Key behaviors aligned with the legacy repo:
- Uses `.env` env-map (names follow legacy)
- ECS bootstrap runs a one-off `run-task` reusing the ECS service network configuration (subnets + SGs)
- Recurring Spark schedule uses EventBridge->ECS RunTask (Terraform-managed), while the API container can still run a safety-net scheduler
- Secrets are stored in Secrets Manager (containers created by TF; values set by tools/aws/ensure_secrets.py)

Flow:
1) doctor
2) bootstrap backend (S3 bucket; optional DDB table if configured)
3) apply shared durable (VPC + Secrets containers)
4) apply shared nondurable (buckets + ECR)
5) ensure secrets values
6) build & push images
7) apply kube/nonkube stack
8) bootstrap analytics once:
   - kube: applies k8s Job then CronJob
   - nonkube: runs ECS one-off task override against the service task def
"""
import argparse, os, subprocess, json
from tools._env import load_dotenv, require
from tools.tofu_runner import tofu
from tools.aws._backend import backend_config

from tools import logger
from tools.aws._aws_vars import get_base_vars

load_dotenv()

def init_stack(stack_dir: str, env: str):
    cfg = backend_config(stack_dir, env)
    args = ["init","-upgrade","-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    tofu(args, cwd=stack_dir, check=True)

def apply_stack(stack_dir: str, env: str, extra_vars: list[str]):
    with logger.Heartbeat(f"Applying stack: {stack_dir}"):
        init_stack(stack_dir, env)
        base = get_base_vars(env)
        tofu(["apply","-auto-approve"] + base + extra_vars, cwd=stack_dir, check=True)

def tofu_output_json(stack_dir: str, env: str):
    init_stack(stack_dir, env)
    out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd=stack_dir, text=True)
    return json.loads(out)

def aws_json(cmd):
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)

def run_ecs_bootstrap(env: str):
    region = require("AWS_REGION")
    
    with logger.Heartbeat("Executing ECS analytics bootstrap"):
        # discover outputs from terraform
        out = tofu_output_json("deploy-aws/nonkube", env)
        
        # Resolve Cluster and Service names
        cluster = out.get("ecs_cluster_name", {}).get("value")
        if not cluster:
             cluster = os.getenv("ECS_CLUSTER_NAME") or f"{require('FRU_PREFIX')}-{env}-ecs"
             
        svc = out.get("ecs_service_name", {}).get("value") or f"{require('FRU_PREFIX')}-{env}-api-svc"

        svc_desc = aws_json(["aws","ecs","describe-services","--cluster",cluster,"--services",svc,"--region",region])
        service = svc_desc["services"][0]
        task_def_arn = service["taskDefinition"]
        net = service.get("networkConfiguration",{}).get("awsvpcConfiguration",{})
        subnets = net.get("subnets",[])
        sgs = net.get("securityGroups",[])

        if not subnets:
            raise SystemExit("Could not determine ECS service subnets for bootstrap.")

        # Container name: first container in task def (legacy approach)
        td = aws_json(["aws","ecs","describe-task-definition","--task-definition",task_def_arn,"--region",region])
        container_name = td["taskDefinition"]["containerDefinitions"][0]["name"]

        # Override command to run analytics once (legacy working pattern)
        overrides = {
          "containerOverrides": [{
            "name": container_name,
            "command": ["python", "/app/spark_jobs/utils/run_analytics_once.py"]
          }]
        }

        net_cfg = {"awsvpcConfiguration": {"subnets": subnets, "assignPublicIp":"DISABLED"}}
        if sgs:
            net_cfg["awsvpcConfiguration"]["securityGroups"] = sgs

        logger.info("Running one-off ECS analytics bootstrap task (non-blocking)...")
        subprocess.run([
            "aws","ecs","run-task",
            "--cluster",cluster,
            "--task-definition",task_def_arn,
            "--launch-type","FARGATE",
            "--network-configuration", json.dumps(net_cfg),
            "--overrides", json.dumps(overrides),
            "--region", region,
        ], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube","nonkube"], required=True)
    ap.add_argument("--env", default=os.getenv("ENVIRONMENT", os.getenv("FRU_ENV","dev")))
    ap.add_argument("--skip-doctor", action="store_true")
    args = ap.parse_args()

    # Fail fast on all support scripts
    if not args.skip_doctor:
        subprocess.run(["python","tools/aws/doctor.py","--env",args.env], check=True)
    subprocess.run(["python","tools/aws/bootstrap_state_backend.py"], check=True)

    # shared durable
    apply_stack("deploy-aws/shared/durable", args.env, [
        "-var", 'azs=["us-east-1a","us-east-1b"]',
        "-var", 'public_subnet_cidrs=["10.0.1.0/24","10.0.2.0/24"]',
        "-var", 'private_subnet_cidrs=["10.0.101.0/24","10.0.102.0/24"]',
        "-var", "allow_destroy_durable=false",
    ])

    # shared nondurable
    apply_stack("deploy-aws/shared/nondurable", args.env, [])

    subprocess.run(["python","tools/aws/ensure_secrets.py","--env",args.env], check=True)
    
    with logger.Heartbeat("Building and pushing images"):
        subprocess.run(["python","tools/aws/build_and_push_images.py","--env",args.env], check=True)

    # Get ECR URLs from state
    snd = tofu_output_json("deploy-aws/shared/nondurable", args.env)
    app_repo_url = snd["ecr_app_url"]["value"]
    spark_repo_url = snd["ecr_spark_url"]["value"]
    spark_image_full = f"{spark_repo_url}:{require('SPARK_IMAGE_TAG')}"
    app_image_full = f"{app_repo_url}:{require('APP_IMAGE_TAG')}"

    if args.scope == "kube":
        apply_stack("deploy-aws/kube", args.env, [
            "-var", f"eks_instance_types=[\"{require('EKS_NODE_INSTANCE_TYPES')}\"]",
            "-var", f"eks_desired_nodes={require('EKS_DESIRED_NODES')}",
        ])
        subprocess.run(["python","tools/aws/kube_apply.py","--env",args.env,"--phase","bootstrap","--spark-image",spark_image_full,"--app-image",app_image_full], check=True)
        subprocess.run(["python","tools/aws/kube_apply.py","--env",args.env,"--phase","schedule","--spark-image",spark_image_full], check=True)
    else:
        apply_stack("deploy-aws/nonkube", args.env, [
            "-var", f"app_image={app_repo_url}:{require('APP_IMAGE_TAG')}",
            "-var", f"spark_image={spark_image_full}",
        ])

        run_ecs_bootstrap(args.env)

    logger.success("Deployment sequence complete.")

if __name__ == "__main__":
    main()