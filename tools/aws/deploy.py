"""
AWS Deploy Orchestrator (legacy-aware, best-practice simplification)

Usage:
  python tools/aws/deploy.py --scope kube --env dev
  python tools/aws/deploy.py --scope nonkube --env dev
  python tools/aws/deploy.py --scope all --env dev

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

Scope "all": deploys nonkube first, then kube (idempotent, shared phases run once).
"""
import argparse
import os
import subprocess
import sys
import time

from tools._env import load_dotenv, require
from tools.aws.common.core.backend import resolve_region
from tools.common.logging import logger
from tools.phases import PhaseTracker, deploy_phases
from tools.common.stats import DeployStats, scope_for
from tools.aws.common.deploy.deploy_common import tofu_output_json
from tools.aws.kube.deploy_kube import run_deploy_kube
from tools.aws.nonkube.deploy_nonkube import run_deploy_nonkube
from tools.aws.common.deploy.bootstrap_helpers import K8S_NAMESPACE

load_dotenv()


def _print_success_url(env: str, region: str, scope: str) -> None:
    """Print deployment success and frontend URL."""
    try:
        logger.info("Retrieving frontend URL...")
        if scope in ("kube", "all"):
            stack_out = tofu_output_json("live-deploy-aws/kube", env, region)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            if cf_domain:
                frontend_url = f"https://{cf_domain}"
                _log_success(frontend_url)
                return
            # Fallback: LB hostname
            lb_host = ""
            for attempt in range(12):
                try:
                    lb_host = subprocess.check_output([
                        "kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE,
                        "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}",
                    ], text=True).strip()
                    if lb_host:
                        break
                except Exception:
                    pass
                if attempt < 11:
                    time.sleep(10)
            if lb_host:
                _log_success(f"http://{lb_host}")
                return

        if scope in ("nonkube", "all"):
            stack_out = tofu_output_json("live-deploy-aws/nonkube", env, region)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            alb_dns = stack_out.get("alb_dns_name", {}).get("value")
            if cf_domain:
                frontend_url = f"https://{cf_domain}"
                _log_success(frontend_url, alb_dns=alb_dns)
                return
            if alb_dns:
                _log_success(f"http://{alb_dns}")
    except Exception as e:
        logger.warning(f"Could not retrieve frontend URL: {e}")


def _log_success(frontend_url: str, alb_dns: str | None = None) -> None:
    logger.success(f"\n{'='*70}")
    logger.success("✓ DEPLOYMENT COMPLETE - READY FOR TESTING")
    logger.success(f"{'='*70}")
    logger.success(f"\n🌐 CloudFront URL: {frontend_url}")
    logger.success(f"   Health Check: {frontend_url}/health")
    logger.success(f"   API Version: {frontend_url}/version")
    logger.success(f"\n   Open in browser: {frontend_url}")
    if alb_dns:
        logger.success(f"   (Direct ALB: http://{alb_dns})")
    logger.success(f"{'='*70}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scope",
        choices=["kube", "nonkube", "all"],
        default=os.getenv("DEFAULT_SCOPE", "nonkube"),
        help="Deploy scope (default: DEFAULT_SCOPE from .env or nonkube)",
    )
    ap.add_argument("--env", default=os.getenv("ENVIRONMENT", os.getenv("FRU_ENV", "dev")))
    ap.add_argument("--region", default="", help="Region (default: CLOUD_REGION)")
    ap.add_argument("--skip-doctor", action="store_true")
    ap.add_argument("--force-spark-rebuild", action="store_true", help="Build Spark image with --no-cache")
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
    stats = DeployStats()

    # War Story 44: Require PGPASSWORD when deploying kube/nonkube
    if scope in ("kube", "nonkube", "all") and not os.getenv("PGPASSWORD"):
        logger.error("PGPASSWORD must be set in .env when deploying kube/nonkube.")
        logger.error("Aurora and db_password_plain in Secrets Manager must use the same password.")
        logger.error("See README_WAR_STORIES.md ## 44 for resolution steps.")
        raise SystemExit(1)

    try:
        # Phase 1: Doctor
        tracker.start_phase(1)
        stats.set_scope("shared")
        if not args.skip_doctor:
            logger.step(f"[1/{len(phases)}] Running doctor checks...")
            with stats.timed("Doctor", "doctor checks"):
                subprocess.run(
                    ["python", "tools/aws/standalone/doctor.py", "--env", env, "--region", region, "--scope", scope],
                    check=True,
                    env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region},
                )
            logger.success("Doctor OK")
        else:
            logger.info(f"[1/{len(phases)}] Skipping doctor checks")
        tracker.end_phase(1)

        # Phase 2: Backend
        tracker.start_phase(2)
        logger.step(f"[2/{len(phases)}] Bootstrapping state backend...")
        with stats.timed("Backend", "bootstrap_state_backend"):
            subprocess.run(["python", "tools/aws/common/deploy/bootstrap_state_backend.py"], check=True)
        logger.success("Backend bootstrapped")
        tracker.end_phase(2)

        # Phase 3: Shared durable
        tracker.start_phase(3)
        logger.step(f"[3/{len(phases)}] Applying shared durable stack (VPC + Aurora + Secrets)...")
        from tools.aws.common.deploy.deploy_common import apply_stack

        aurora_pw = os.getenv("PGPASSWORD") or ""
        durable_vars = [
            "-var", 'azs=["us-east-1a","us-east-1b"]',
            "-var", 'public_subnet_cidrs=["10.0.1.0/24","10.0.2.0/24"]',
            "-var", 'private_subnet_cidrs=["10.0.101.0/24","10.0.102.0/24"]',
            "-var", "allow_destroy_durable=false",
        ]
        if aurora_pw:
            durable_vars += ["-var", f"aurora_master_password={aurora_pw}"]
        else:
            logger.warning("PGPASSWORD not set; Aurora creation may fail. Set in .env before deploy.")
        with stats.timed("Tofu apply", "live-deploy-aws/shared/durable"):
            apply_stack("live-deploy-aws/shared/durable", env, durable_vars, region)
        logger.success("Shared durable applied")
        tracker.end_phase(3)

        # Phase 4: Shared nondurable
        tracker.start_phase(4)
        logger.step(f"[4/{len(phases)}] Applying shared nondurable stack (ECR + S3)...")
        with stats.timed("Tofu apply", "live-deploy-aws/shared/nondurable"):
            apply_stack("live-deploy-aws/shared/nondurable", env, [], region)
        logger.success("Shared nondurable applied")
        tracker.end_phase(4)

        # Phase 5: Secrets
        tracker.start_phase(5)
        logger.step(f"[5/{len(phases)}] Ensuring secrets in Secrets Manager...")
        with stats.timed("Secrets", "ensure_secrets"):
            subprocess.run(
                ["python", "tools/aws/common/deploy/ensure_secrets.py", "--env", env, "--region", region],
                check=True,
                env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region},
            )
        logger.success("Secrets ensured")
        tracker.end_phase(5)

        # Phase 6: Database setup
        tracker.start_phase(6)
        logger.step(f"[6/{len(phases)}] Setting up database (pgvector, schema, data)...")
        try:
            with stats.timed("Database", "setup_database"):
                subprocess.run(
                    ["python", "tools/aws/common/deploy/setup_database.py", "--env", env, "--region", region],
                    check=True,
                    env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region},
                )
            logger.success("Database setup complete")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Database setup had issues (may already be initialized): {e}")
        tracker.end_phase(6)

        # Phase 7: Build & push
        tracker.start_phase(7)
        logger.step(f"[7/{len(phases)}] Building and pushing images...")
        build_env = {**os.environ, "CLOUD_REGION": region, "AWS_REGION": region}
        build_env["PYTHONUNBUFFERED"] = "1"
        build_cmd = ["python", "tools/aws/common/deploy/build_and_push_images.py", "--env", env, "--region", region]
        if args.force_spark_rebuild:
            build_cmd.append("--no-cache")
        with stats.timed("Build & push", "build_and_push_images"):
            proc = subprocess.run(build_cmd, cwd=os.getcwd(), env=build_env)
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

        # Scope-specific deploy: nonkube first when scope=all, then kube
        if scope == "all":
            phase_idx = 8
            phase_idx += 1
            tracker.start_phase(phase_idx)
            run_deploy_nonkube(env, region, snd, app_image_full, spark_image_full, args, stats=stats)
            tracker.end_phase(phase_idx)

            phase_idx += 1
            tracker.start_phase(phase_idx)
            run_deploy_kube(env, region, snd, app_image_full, spark_image_full, args, stats=stats)
            tracker.end_phase(phase_idx)
        elif scope == "kube":
            tracker.start_phase(9)
            run_deploy_kube(env, region, snd, app_image_full, spark_image_full, args, stats=stats)
            tracker.end_phase(9)
        else:
            # scope == "nonkube"
            tracker.start_phase(9)
            run_deploy_nonkube(env, region, snd, app_image_full, spark_image_full, args, stats=stats)
            tracker.end_phase(9)

        stats.print_summary()
        logger.success(f"✓ Deployment sequence complete! Scope: {scope}, Env: {env}")
        _print_success_url(env, region, scope)
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
