
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
import argparse, os, subprocess, json, sys
from tools._env import load_dotenv, require
from tools.tofu_runner import tofu
from tools.aws._backend import backend_config

from tools import logger
from tools.aws._aws_vars import get_base_vars

load_dotenv()

def init_stack(stack_dir: str, env: str):
    logger.info(f"[INIT] {stack_dir}")
    cfg = backend_config(stack_dir, env)
    args = ["init","-upgrade","-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    try:
        tofu(args, cwd=stack_dir, check=True)
        logger.success(f"[INIT OK] {stack_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[INIT FAILED] {stack_dir}: {e}")
        raise

def apply_stack(stack_dir: str, env: str, extra_vars: list[str]):
    logger.step(f"Applying stack: {stack_dir}")
    try:
        init_stack(stack_dir, env)
        base = get_base_vars(env)
        logger.info(f"[APPLY] Running tofu apply with base vars: {base} + extra vars: {extra_vars}")
        tofu(["apply","-auto-approve"] + base + extra_vars, cwd=stack_dir, check=True)
        logger.success(f"[APPLY OK] {stack_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[APPLY FAILED] {stack_dir}: {e}")
        raise
    except Exception as e:
        logger.error(f"[APPLY ERROR] {stack_dir}: {e}")
        raise

def tofu_output_json(stack_dir: str, env: str):
    logger.info(f"[OUTPUT] Getting outputs from {stack_dir}")
    try:
        init_stack(stack_dir, env)
        out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd=stack_dir, text=True)
        logger.success(f"[OUTPUT OK] {stack_dir}")
        return json.loads(out)
    except subprocess.CalledProcessError as e:
        logger.error(f"[OUTPUT FAILED] {stack_dir}: {e}")
        raise
    except Exception as e:
        logger.error(f"[OUTPUT ERROR] {stack_dir}: {e}")
        raise

def aws_json(cmd):
    logger.info(f"[AWS] Running: {' '.join(cmd)}")
    try:
        out = subprocess.check_output(cmd, text=True)
        result = json.loads(out)
        logger.success(f"[AWS OK]")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"[AWS FAILED]: {e}")
        raise
    except Exception as e:
        logger.error(f"[AWS ERROR]: {e}")
        raise

def run_ecs_bootstrap(env: str):
    region = require("AWS_REGION")
    
    logger.step("Executing ECS analytics bootstrap")
    try:
        # discover outputs from terraform
        logger.info("[ECS BOOTSTRAP] Getting terraform outputs...")
        out = tofu_output_json("deploy-aws/nonkube", env)
        
        # Resolve Cluster and Service names
        cluster = out.get("ecs_cluster_name", {}).get("value")
        if not cluster:
             cluster = os.getenv("ECS_CLUSTER_NAME") or f"{require('FRU_PREFIX')}-{env}-ecs"
        
        logger.info(f"[ECS BOOTSTRAP] Cluster: {cluster}")
        
        svc = out.get("ecs_service_name", {}).get("value") or f"{require('FRU_PREFIX')}-{env}-api-svc"
        logger.info(f"[ECS BOOTSTRAP] Service: {svc}")

        logger.info("[ECS BOOTSTRAP] Describing service...")
        svc_desc = aws_json(["aws","ecs","describe-services","--cluster",cluster,"--services",svc,"--region",region])
        service = svc_desc["services"][0]
        task_def_arn = service["taskDefinition"]
        net = service.get("networkConfiguration",{}).get("awsvpcConfiguration",{})
        subnets = net.get("subnets",[])
        sgs = net.get("securityGroups",[])

        if not subnets:
            raise SystemExit("Could not determine ECS service subnets for bootstrap.")

        logger.info(f"[ECS BOOTSTRAP] Task def: {task_def_arn}")
        logger.info(f"[ECS BOOTSTRAP] Subnets: {subnets}")

        # Container name: first container in task def (legacy approach)
        logger.info("[ECS BOOTSTRAP] Getting task definition...")
        td = aws_json(["aws","ecs","describe-task-definition","--task-definition",task_def_arn,"--region",region])
        container_name = td["taskDefinition"]["containerDefinitions"][0]["name"]
        logger.info(f"[ECS BOOTSTRAP] Container: {container_name}")

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

        logger.info("[ECS BOOTSTRAP] Starting one-off ECS task...")
        try:
            # Capture output to prevent buffering hangs and log only if needed
            proc = subprocess.run([
                "aws","ecs","run-task",
                "--cluster",cluster,
                "--task-definition",task_def_arn,
                "--launch-type","FARGATE",
                "--network-configuration", json.dumps(net_cfg),
                "--overrides", json.dumps(overrides),
                "--region", region,
            ], check=True, capture_output=True, text=True, timeout=60)
            
            # Log success but don't dump huge JSON
            logger.success("ECS bootstrap task started successfully.")
            logger.info(f"[ECS BOOTSTRAP] Task info: {proc.stdout[:200]}...")
            
        except subprocess.TimeoutExpired:
            logger.error("AWS ECS run-task timed out (CLI hang).")
            # If it timed out, task might have started anyway.
        except subprocess.CalledProcessError as e:
            logger.error(f"[ECS BOOTSTRAP FAILED] Failed to run ECS task: {e.stderr}")
            raise
    except Exception as e:
        logger.error(f"[ECS BOOTSTRAP ERROR] {e}")
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube","nonkube"], required=True)
    ap.add_argument("--env", default=os.getenv("ENVIRONMENT", os.getenv("FRU_ENV","dev")))
    ap.add_argument("--skip-doctor", action="store_true")
    args = ap.parse_args()

    env = args.env
    scope = args.scope
    
    logger.step(f"Starting deployment: scope={scope} env={env}")

    try:
        # Fail fast on all support scripts
        if not args.skip_doctor:
            logger.step("[1/9] Running doctor checks...")
            subprocess.run(["python","tools/aws/doctor.py","--env",env], check=True)
            logger.success("[1/9] Doctor OK")
        else:
            logger.info("[1/9] Skipping doctor checks")
        
        logger.step("[2/9] Bootstrapping state backend...")
        subprocess.run(["python","tools/aws/bootstrap_state_backend.py"], check=True)
        logger.success("[2/9] Backend bootstrapped")

        # shared durable
        logger.step("[3/9] Applying shared durable stack (VPC + Secrets)...")
        apply_stack("deploy-aws/shared/durable", env, [
            "-var", 'azs=["us-east-1a","us-east-1b"]',
            "-var", 'public_subnet_cidrs=["10.0.1.0/24","10.0.2.0/24"]',
            "-var", 'private_subnet_cidrs=["10.0.101.0/24","10.0.102.0/24"]',
            "-var", "allow_destroy_durable=false",
        ])
        logger.success("[3/9] Shared durable applied")

        # shared nondurable
        logger.step("[4/9] Applying shared nondurable stack (ECR + S3)...")
        apply_stack("deploy-aws/shared/nondurable", env, [])
        logger.success("[4/9] Shared nondurable applied")

        logger.step("[5/9] Ensuring secrets in Secrets Manager...")
        subprocess.run(["python","tools/aws/ensure_secrets.py","--env",env], check=True)
        logger.success("[5/9] Secrets ensured")
        
        logger.step("[6/9] Building and pushing images...")
        subprocess.run(["python","tools/aws/build_and_push_images.py","--env",env], check=True)
        logger.success("[6/9] Images built and pushed")

        # Get ECR URLs from state
        logger.step("[7/9] Getting ECR image URLs...")
        snd = tofu_output_json("deploy-aws/shared/nondurable", env)
        app_repo_url = snd["ecr_app_url"]["value"]
        spark_repo_url = snd["ecr_spark_url"]["value"]
        spark_image_full = f"{spark_repo_url}:{require('SPARK_IMAGE_TAG')}"
        app_image_full = f"{app_repo_url}:{require('APP_IMAGE_TAG')}"
        logger.info(f"[7/9] App image: {app_image_full}")
        logger.info(f"[7/9] Spark image: {spark_image_full}")
        logger.success("[7/9] ECR URLs obtained")

        if scope == "kube":
            logger.step("[8/9] Applying EKS stack...")
            apply_stack("deploy-aws/kube", env, [
                "-var", f"eks_instance_types=[\"{require('EKS_NODE_INSTANCE_TYPES')}\"]",
                "-var", f"eks_desired_nodes={require('EKS_DESIRED_NODES')}",
            ])
            logger.success("[8/9] EKS stack applied")
            
            logger.step("[9/9] Running Kubernetes bootstrap and schedule...")
            subprocess.run(["python","tools/aws/kube_apply.py","--env",env,"--phase","bootstrap","--spark-image",spark_image_full,"--app-image",app_image_full], check=True)
            subprocess.run(["python","tools/aws/kube_apply.py","--env",env,"--phase","schedule","--spark-image",spark_image_full], check=True)
            logger.success("[9/9] Kubernetes bootstrap and schedule complete")
            
            # Get K8s LoadBalancer URL for manual testing
            try:
                logger.info("Retrieving frontend URL...")
                import time as time_module
                lb_host = ""
                for attempt in range(12):  # Try for up to 2 minutes
                    try:
                        lb_host = subprocess.check_output([
                            "kubectl", "get", "svc", "fru-api-svc", "-n", "fru",
                            "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"
                        ], text=True).strip()
                        if lb_host:
                            break
                    except:
                        pass
                    if attempt < 11:
                        time_module.sleep(10)
                
                if lb_host:
                    frontend_url = f"http://{lb_host}"
                    logger.success(f"\n{'='*70}")
                    logger.success(f"✓ DEPLOYMENT COMPLETE - READY FOR TESTING")
                    logger.success(f"{'='*70}")
                    logger.success(f"\n🌐 Frontend URL: {frontend_url}")
                    logger.success(f"   Health Check: {frontend_url}/health")
                    logger.success(f"   API Version: {frontend_url}/version")
                    logger.success(f"\n   Open in browser: {frontend_url}")
                    logger.success(f"{'='*70}\n")
                else:
                    logger.warning("LoadBalancer URL not yet available (may take a few minutes)")
            except Exception as e:
                logger.warning(f"Could not retrieve frontend URL: {e}")
        else:
            logger.step("[8/9] Applying ECS stack...")
            apply_stack("deploy-aws/nonkube", env, [
                "-var", f"app_image={app_repo_url}:{require('APP_IMAGE_TAG')}",
                "-var", f"spark_image={spark_image_full}",
            ])
            logger.success("[8/9] ECS stack applied")

            logger.step("[9/9] Running ECS bootstrap...")
            run_ecs_bootstrap(env)
            logger.success("[9/9] ECS bootstrap complete")
            
            # Get ALB DNS for manual testing
            try:
                logger.info("Retrieving frontend URL...")
                stack_out = tofu_output_json("deploy-aws/nonkube", env)
                alb_dns = stack_out.get("alb_dns_name", {}).get("value")
                if alb_dns:
                    frontend_url = f"http://{alb_dns}"
                    logger.success(f"\n{'='*70}")
                    logger.success(f"✓ DEPLOYMENT COMPLETE - READY FOR TESTING")
                    logger.success(f"{'='*70}")
                    logger.success(f"\n🌐 Frontend URL: {frontend_url}")
                    logger.success(f"   Health Check: {frontend_url}/health")
                    logger.success(f"   API Version: {frontend_url}/version")
                    logger.success(f"\n   Open in browser: {frontend_url}")
                    logger.success(f"{'='*70}\n")
            except Exception as e:
                logger.warning(f"Could not retrieve frontend URL: {e}")

        logger.success(f"✓ Deployment sequence complete! Scope: {scope}, Env: {env}")
        sys.exit(0)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed at step: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deployment error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()