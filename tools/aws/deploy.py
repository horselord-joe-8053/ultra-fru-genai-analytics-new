
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
from tools.aws._backend import backend_config, resolve_region

from tools import logger
from tools.aws._aws_vars import get_base_vars
from tools.phases import PhaseTracker, deploy_phases
from tools.subprocess_retry import run_with_retry
from tools.tofu_runner import get_tofu_env
from tools.aws.bootstrap_helpers import check_ecs_bootstrap_succeeded, K8S_NAMESPACE
from tools.aws.deploy_frontend import deploy_frontend_to_s3

load_dotenv()

def init_stack(stack_dir: str, env: str, region: str | None = None):
    logger.info(f"[INIT] {stack_dir}")
    cfg = backend_config(stack_dir, env, region)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe] + args
    try:
        run_with_retry(cmd, cwd=stack_dir, env=get_tofu_env(region), description=f"tofu init in {stack_dir}")
        logger.success(f"[INIT OK] {stack_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[INIT FAILED] {stack_dir}: {e}")
        raise

def apply_stack(stack_dir: str, env: str, extra_vars: list[str], region: str | None = None):
    logger.step(f"Applying stack: {stack_dir}")
    try:
        init_stack(stack_dir, env, region)
        get_base_vars(env, region)
        base = []  # get_base_vars sets TF_VAR_ in env
        logger.info(f"[APPLY] Running tofu apply with base vars + extra vars: {extra_vars}")
        tofu(["apply","-auto-approve"] + base + extra_vars, cwd=stack_dir, check=True)
        logger.success(f"[APPLY OK] {stack_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[APPLY FAILED] {stack_dir}: {e}")
        raise
    except Exception as e:
        logger.error(f"[APPLY ERROR] {stack_dir}: {e}")
        raise

def tofu_output_json(stack_dir: str, env: str, region: str | None = None):
    logger.info(f"[OUTPUT] Getting outputs from {stack_dir}")
    try:
        init_stack(stack_dir, env, region)
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN","tofu"),"output","-json"],
            cwd=stack_dir, text=True, env=get_tofu_env(region)
        )
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

def run_ecs_bootstrap(env: str, region: str | None = None):
    region = region or os.getenv("CLOUD_REGION", "").strip() or require("AWS_REGION")

    if check_ecs_bootstrap_succeeded(env):
        logger.success("[ECS BOOTSTRAP] Skip: bootstrap already succeeded (idempotent)")
        return

    logger.step("Executing ECS analytics bootstrap")
    try:
        # discover outputs from terraform
        logger.info("[ECS BOOTSTRAP] Getting terraform outputs...")
        out = tofu_output_json("live-deploy-aws/nonkube", env, region)
        
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
    ap.add_argument("--region", default="", help="Region (default: CLOUD_REGION)")
    ap.add_argument("--skip-doctor", action="store_true")
    args = ap.parse_args()

    env = args.env
    scope = args.scope
    region = resolve_region(args.region or None)
    os.environ["CLOUD_REGION"] = region
    os.environ["AWS_REGION"] = region
    os.environ["AWS_DEFAULT_REGION"] = region

    logger.step(f"Starting deployment: scope={scope} env={env} region={region}")
    phases = deploy_phases(scope)
    tracker = PhaseTracker("Deploy", phases)

    try:
        # Phase 1: Doctor
        tracker.start_phase(1)
        if not args.skip_doctor:
            logger.step(f"[1/{len(phases)}] Running doctor checks...")
            subprocess.run(["python","tools/aws/doctor.py","--env",env,"--region",region], check=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region})
            logger.success("Doctor OK")
        else:
            logger.info(f"[1/{len(phases)}] Skipping doctor checks")
        tracker.end_phase(1)

        # Phase 2: Backend
        tracker.start_phase(2)
        logger.step(f"[2/{len(phases)}] Bootstrapping state backend...")
        subprocess.run(["python","tools/aws/bootstrap_state_backend.py"], check=True)
        logger.success("Backend bootstrapped")
        tracker.end_phase(2)

        # Phase 3: Shared durable
        tracker.start_phase(3)
        logger.step(f"[3/{len(phases)}] Applying shared durable stack (VPC + Aurora + Secrets)...")
        aurora_pw = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD") or ""
        durable_vars = [
            "-var", 'azs=["us-east-1a","us-east-1b"]',
            "-var", 'public_subnet_cidrs=["10.0.1.0/24","10.0.2.0/24"]',
            "-var", 'private_subnet_cidrs=["10.0.101.0/24","10.0.102.0/24"]',
            "-var", "allow_destroy_durable=false",
        ]
        if aurora_pw:
            durable_vars += ["-var", f"aurora_master_password={aurora_pw}"]
        else:
            logger.warning("DB_PASSWORD/PGPASSWORD not set; Aurora creation may fail. Set in .env before deploy.")
        apply_stack("live-deploy-aws/shared/durable", env, durable_vars, region)
        logger.success("Shared durable applied")
        tracker.end_phase(3)

        # Phase 4: Shared nondurable
        tracker.start_phase(4)
        logger.step(f"[4/{len(phases)}] Applying shared nondurable stack (ECR + S3)...")
        apply_stack("live-deploy-aws/shared/nondurable", env, [], region)
        logger.success("Shared nondurable applied")
        tracker.end_phase(4)

        # Phase 5: Secrets
        tracker.start_phase(5)
        logger.step(f"[5/{len(phases)}] Ensuring secrets in Secrets Manager...")
        subprocess.run(["python","tools/aws/ensure_secrets.py","--env",env,"--region",region], check=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region})
        logger.success("Secrets ensured")
        tracker.end_phase(5)

        # Phase 6: Database setup
        tracker.start_phase(6)
        logger.step(f"[6/{len(phases)}] Setting up database (pgvector, schema, data)...")
        try:
            subprocess.run(["python","tools/aws/setup_database.py","--env",env,"--region",region], check=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region})
            logger.success("Database setup complete")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Database setup had issues (may already be initialized): {e}")
        tracker.end_phase(6)

        # Phase 7: Build & push (build_and_push has its own per-step progress: 1/4, 2/4, etc.)
        tracker.start_phase(7)
        logger.step(f"[7/{len(phases)}] Building and pushing images...")
        build_env = {**os.environ, "CLOUD_REGION": region, "AWS_REGION": region}
        build_env["PYTHONUNBUFFERED"] = "1"  # Flush output immediately (avoids silent hang when run under Cursor/CI)
        proc = subprocess.run(
            ["python", "tools/aws/build_and_push_images.py", "--env", env, "--region", region],
            cwd=os.getcwd(),
            env=build_env,
        )
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, proc.args)
        logger.success("Images built and pushed")
        tracker.end_phase(7)

        # Phase 8: ECR URLs
        tracker.start_phase(8)
        logger.step(f"[8/{len(phases)}] Getting ECR image URLs...")
        snd = tofu_output_json("live-deploy-aws/shared/nondurable", env, region)
        app_repo_url = snd["ecr_app_url"]["value"]
        spark_repo_url = snd["ecr_spark_url"]["value"]
        spark_image_full = f"{spark_repo_url}:{require('SPARK_IMAGE_TAG')}"
        app_image_full = f"{app_repo_url}:{require('APP_IMAGE_TAG')}"
        logger.info(f"App image: {app_image_full}")
        logger.info(f"Spark image: {spark_image_full}")
        logger.success("ECR URLs obtained")
        tracker.end_phase(8)

        if scope == "kube":
            tracker.start_phase(9)
            logger.step(f"[9/{len(phases)}] Applying EKS stack...")
            apply_stack("live-deploy-aws/kube", env, [
                "-var", f"eks_instance_types=[\"{require('EKS_NODE_INSTANCE_TYPES')}\"]",
                "-var", f"eks_desired_nodes={require('EKS_DESIRED_NODES')}",
            ], region)
            logger.success("EKS stack applied")
            tracker.end_phase(9)

            tracker.start_phase(10)
            logger.step(f"[10/{len(phases)}] Running Kubernetes bootstrap and schedule...")
            delta_bucket = snd["delta_bucket"]["value"]
            durable = tofu_output_json("live-deploy-aws/shared/durable", env, region)
            aurora_endpoint = durable.get("aurora_endpoint", {}).get("value", "")
            db_secret_arn = durable.get("db_password_secret_arn", {}).get("value", "")
            openai_secret_arn = durable.get("openai_api_key_secret_arn", {}).get("value", "")
            region = os.getenv("CLOUD_REGION", os.getenv("AWS_REGION", "us-east-1"))
            delta_table_path = f"s3a://{delta_bucket}/delta/fru_sales"
            kube_apply_args = [
                "python", "tools/aws/kube_apply.py", "--env", env, "--region", region, "--phase", "bootstrap",
                "--spark-image", spark_image_full, "--app-image", app_image_full,
                "--delta-bucket", delta_bucket,
                "--pg-host", aurora_endpoint or "localhost",
                "--pg-port", str(durable.get("aurora_port", {}).get("value", 5432)),
                "--pg-database", durable.get("aurora_database_name", {}).get("value", "fru_db"),
                "--pg-user", "postgres",
                "--aws-region", region,
                "--delta-table-path", delta_table_path,
            ]
            if db_secret_arn:
                kube_apply_args += ["--db-secret-arn", db_secret_arn]
            if openai_secret_arn:
                kube_apply_args += ["--openai-secret-arn", openai_secret_arn]
            bedrock_profile = os.getenv("AWS_BEDROCK_INFERENCE_PROFILE_ID", "")
            bedrock_model = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")
            if bedrock_profile:
                kube_apply_args += ["--bedrock-inference-profile-id", bedrock_profile]
            if bedrock_model:
                kube_apply_args += ["--bedrock-model-id", bedrock_model]
            subprocess.run(kube_apply_args, check=True)
            subprocess.run([
                "python", "tools/aws/kube_apply.py", "--env", env, "--region", region, "--phase", "schedule",
                "--spark-image", spark_image_full, "--delta-bucket", delta_bucket,
            ], check=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region})
            logger.success("Kubernetes bootstrap and schedule complete")
            tracker.end_phase(10)

            # Deploy frontend to S3 (kube parity with nonkube)
            try:
                stack_out = tofu_output_json("live-deploy-aws/kube", env, region)
                frontend_bucket = stack_out.get("frontend_s3_bucket_id", {}).get("value")
                if frontend_bucket:
                    deploy_frontend_to_s3(frontend_bucket, env)
                else:
                    logger.warning("frontend_s3_bucket_id not found; skipping kube frontend deploy")
            except Exception as e:
                logger.warning(f"Could not deploy kube frontend: {e}")

            # Get CloudFront / K8s LoadBalancer URL for manual testing
            try:
                logger.info("Retrieving frontend URL...")
                stack_out = tofu_output_json("live-deploy-aws/kube", env, region)
                cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
                if cf_domain:
                    frontend_url = f"https://{cf_domain}"
                    logger.success(f"\n{'='*70}")
                    logger.success(f"✓ DEPLOYMENT COMPLETE - READY FOR TESTING")
                    logger.success(f"{'='*70}")
                    logger.success(f"\n🌐 CloudFront URL: {frontend_url}")
                    logger.success(f"   Health Check: {frontend_url}/health")
                    logger.success(f"   API Version: {frontend_url}/version")
                    logger.success(f"\n   Open in browser: {frontend_url}")
                    logger.success(f"{'='*70}\n")
                else:
                    import time as time_module
                    lb_host = ""
                    for attempt in range(12):  # Try for up to 2 minutes
                        try:
                            lb_host = subprocess.check_output([
                                "kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
                                "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"
                            ], text=True).strip()
                            if lb_host:
                                break
                        except Exception:
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
            tracker.start_phase(9)
            logger.step(f"[9/{len(phases)}] Applying ECS stack...")
            apply_stack("live-deploy-aws/nonkube", env, [
                "-var", f"app_image={app_repo_url}:{require('APP_IMAGE_TAG')}",
                "-var", f"spark_image={spark_image_full}",
            ], region)
            logger.success("ECS stack applied")
            tracker.end_phase(9)

            # Deploy frontend to S3 (build + sync) - matches legacy deploy-frontend.sh; fixes 403 Access Denied
            stack_out = tofu_output_json("live-deploy-aws/nonkube", env, region)
            frontend_bucket = stack_out.get("frontend_s3_bucket_id", {}).get("value")
            if frontend_bucket:
                deploy_frontend_to_s3(frontend_bucket, env)
            else:
                logger.warning("frontend_s3_bucket_id not found; skipping frontend deploy")

            tracker.start_phase(10)
            logger.step(f"[10/{len(phases)}] Running ECS bootstrap...")
            run_ecs_bootstrap(env, region)
            logger.success("ECS bootstrap complete")
            tracker.end_phase(10)

            # Get CloudFront / ALB URLs for manual testing
            try:
                logger.info("Retrieving frontend URL...")
                stack_out = tofu_output_json("live-deploy-aws/nonkube", env, region)
                cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
                alb_dns = stack_out.get("alb_dns_name", {}).get("value")
                if cf_domain:
                    frontend_url = f"https://{cf_domain}"
                    logger.success(f"\n{'='*70}")
                    logger.success(f"✓ DEPLOYMENT COMPLETE - READY FOR TESTING")
                    logger.success(f"{'='*70}")
                    logger.success(f"\n🌐 CloudFront URL: {frontend_url}")
                    logger.success(f"   Health Check: {frontend_url}/health")
                    logger.success(f"   API Version: {frontend_url}/version")
                    logger.success(f"\n   Open in browser: {frontend_url}")
                    if alb_dns:
                        logger.success(f"   (Direct ALB: http://{alb_dns})")
                    logger.success(f"{'='*70}\n")
                elif alb_dns:
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