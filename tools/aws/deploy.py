"""
AWS Deploy Orchestrator (legacy-aware, best-practice simplification)

Usage:
  python tools/aws/deploy.py --scope kube --env dev
  python tools/aws/deploy.py --scope nonkube --env dev
  python tools/aws/deploy.py --scope all --env dev
  python tools/aws/deploy.py --scope all --env dev --skip-build   # Use repo:latest from ECR, no build
  python tools/aws/deploy.py --scope all --env dev --force-build  # Force build (bypass content-based skip)

Build skip: When build-context hash matches stored hash in S3, deploy skips build and uses repo:latest.
Use --force-build when code changed. See docs/learned/cloud_shared/DEPLOY_BUILD_DOCKER.md.

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
import json
import os
import subprocess
import sys
import time

from tools.cloud_shared.env import load_dotenv, require, EnvVarNotFound
from tools.aws.scope_shared.core.backend import resolve_region
from tools.aws.provider_config_handler import get_azs, get_subnet_cidrs
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.phases import PhaseTracker, deploy_phases
from tools.cloud_shared.stats import DeployStats, scope_for
from tools.aws.scope_shared.deploy.deploy_common import tofu_output_json
from tools.aws.kube.deploy_kube import run_deploy_kube
from tools.aws.nonkube.deploy_nonkube import run_deploy_nonkube
from tools.aws.scope_shared.deploy.bootstrap_helpers import K8S_NAMESPACE

load_dotenv()


def _print_success_url(env: str, region: str, scope: str) -> None:
    """Print deployment success and frontend URL."""
    try:
        logger.info("Retrieving frontend URL...")
        if scope in ("kube", "all"):
            stack_out = tofu_output_json("infra_terraform/live_deploy/aws/kube", env, region)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            if cf_domain:
                frontend_url = f"https://{cf_domain}"
                _log_success(frontend_url)
                return
            # Fallback: LB hostname (uses region validation to avoid wrong-region LB)
            # Ensure kubectl context points at target region (avoids "fru-api-svc not found" when querying wrong cluster)
            subprocess.run(
                [sys.executable, "tools/aws/kube/eks_kubeconfig.py", "--env", env, "--region", region],
                check=False,
                env={**os.environ, "CLOUD_REGION": region},
            )
            from tools.aws.kube.deploy_kube import _try_get_lb_hostname
            lb_host = ""
            for attempt in range(12):
                lb_host = _try_get_lb_hostname(env, region)
                if lb_host:
                    break
                if attempt < 11:
                    time.sleep(10)
            if lb_host:
                _log_success(f"http://{lb_host}")
                return

        if scope in ("nonkube", "all"):
            stack_out = tofu_output_json("infra_terraform/live_deploy/aws/nonkube", env, region)
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


def _ecr_has_images(app_repo_name: str, spark_repo_name: str, region: str) -> bool:
    """Return True if target ECR has both app and spark images (tag=latest)."""
    try:
        subprocess.check_output(
            ["aws", "ecr", "describe-images", "--repository-name", app_repo_name,
             "--image-ids", "imageTag=latest", "--region", region],
            stderr=subprocess.DEVNULL, timeout=15,
        )
        subprocess.check_output(
            ["aws", "ecr", "describe-images", "--repository-name", spark_repo_name,
             "--image-ids", "imageTag=latest", "--region", region],
            stderr=subprocess.DEVNULL, timeout=15,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _push_only_for_ecr_absence(env: str, target_region: str, snd: dict) -> None:
    """
    When build was skipped (content-skip or --skip-build): if target ECR does not have
    the images, run push-only so local canonical images are pushed. Avoids
    ImageNotFoundException when deploying to a new region. See DEPLOY_BUILD_DOCKER.md.
    """
    from tools.cloud_shared.docker.push_only_for_registry_absence import push_only_for_registry_absence

    app_repo_url = snd.get("ecr_app_url", {}).get("value", "")
    spark_repo_url = snd.get("ecr_spark_url", {}).get("value", "")
    if not app_repo_url or not spark_repo_url:
        return
    app_repo_name = app_repo_url.split("/")[-1]
    spark_repo_name = spark_repo_url.split("/")[-1]

    def registry_has_images() -> bool:
        return _ecr_has_images(app_repo_name, spark_repo_name, target_region)

    def push_local_images() -> None:
        proc = subprocess.run(
            [sys.executable, "tools/aws/scope_shared/deploy/build_and_push_images.py",
             "--env", env, "--region", target_region, "--push-only"],
            cwd=os.getcwd(),
            env={**os.environ, "CLOUD_REGION": target_region},
        )
        if proc.returncode != 0:
            raise RuntimeError("build_and_push_images --push-only failed")

    push_only_for_registry_absence(registry_has_images, push_local_images, log_prefix="[PUSH-ONLY]")


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
    ap.add_argument("--force-spark-rebuild", action="store_true", help="Build Spark image with --no-cache (deprecated: use --no-cache)")
    ap.add_argument("--no-cache", action="store_true", help="Build all images with Docker --no-cache (cache-free)")
    ap.add_argument("--skip-build", action="store_true", help="Skip build; use repo:latest from ECR and query tags for display")
    ap.add_argument("--force-build", action="store_true",
        help="Force build even when content hash matches (bypasses content-based skip; use when code changed or you want a fresh image)")
    ap.add_argument("--force-refresh-data", action="store_true",
        help="Force reload DB schema and embeddings (drops and repopulates fru_sales_embeddings)")
    ap.add_argument("--elb", action="store_true",
        help="[Kube only] Use in-tree Classic ELB (api-service-elb.yaml) instead of NLB (api-service.yaml). Reverts to pre-migration behavior.")
    args = ap.parse_args()

    env = args.env
    scope = args.scope
    try:
        region = resolve_region(args.region or None)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
    os.environ["CLOUD_REGION"] = region

    deploy_start = time.time()
    logger.operation_start("Deploy", scope, env, region)
    phases = deploy_phases(scope)
    tracker = PhaseTracker("Deploy", phases)
    stats = DeployStats()

    # War Story 44: Require PGPASSWORD when deploying kube/nonkube
    if scope in ("kube", "nonkube", "all") and not os.getenv("PGPASSWORD"):
        logger.error("PGPASSWORD must be set in .env when deploying kube/nonkube.")
        logger.error("Aurora and db_password_plain in Secrets Manager must use the same password.")
        logger.error("See docs/war_stories/WAR_STORIES_AWS.md ## 26 for resolution steps.")
        raise SystemExit(1)

    try:
        # Phase 1: Doctor
        tracker.start_phase(1)
        stats.set_scope("shared")
        if not args.skip_doctor:
            logger.step(f"[1/{len(phases)}] Running doctor checks...")
            doctor_args = ["python", "tools/aws/standalone/doctor.py", "--env", env, "--region", region, "--scope", scope]
            if getattr(args, "elb", False):
                doctor_args.append("--elb")
            with stats.timed("Doctor", "doctor checks"):
                subprocess.run(
                    doctor_args,
                    check=True,
                    env={**os.environ, "CLOUD_REGION": region},
                )
            logger.success("Doctor OK")
        else:
            logger.info(f"[1/{len(phases)}] Skipping doctor checks")
        tracker.end_phase(1)

        # Phase 2: Backend
        tracker.start_phase(2)
        logger.step(f"[2/{len(phases)}] Bootstrapping state backend...")
        with stats.timed("Backend", "bootstrap_state_backend"):
            subprocess.run(["python", "tools/aws/scope_shared/deploy/bootstrap_state_backend.py"], check=True)
        logger.success("Backend bootstrapped")
        tracker.end_phase(2)

        # Phase 3a: Durable-with-cooloff (Secrets Manager only). Applied first so durable
        # can read secret ARNs via terraform_remote_state. See docs/learned/cloud_shared/DURABLE_COOLOFF_MULTI_CLOUD.md.
        tracker.start_phase(3)
        logger.step(f"[3/{len(phases)}] Applying durable_with_cooloff (Secrets)...")
        from tools.aws.scope_shared.deploy.deploy_common import apply_stack, init_stack
        from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
        from tools.aws.scope_shared.import_preexist.durable_cooloff import run_import_durable_cooloff

        get_base_vars(env, region)
        durable_cooloff_dir = "infra_terraform/live_deploy/aws/scope_shared/durable_with_cooloff"
        init_stack(durable_cooloff_dir, env, region)
        run_import_durable_cooloff(durable_cooloff_dir, env, region)
        with stats.timed("Tofu apply", "durable_with_cooloff"):
            apply_stack(durable_cooloff_dir, env, [], region)
        logger.success("Durable-with-cooloff applied")
        tracker.end_phase(3)

        # Phase 3b: Durable (VPC + Aurora). Reads secret ARNs from durable_with_cooloff.
        tracker.start_phase(4)
        logger.step(f"[4/{len(phases)}] Applying shared durable stack (VPC + Aurora)...")
        durable_dir = "infra_terraform/live_deploy/aws/scope_shared/durable"
        init_stack(durable_dir, env, region)
        # Migration: remove secrets from durable state (moved to durable_with_cooloff).
        # Prevents durable apply from destroying them. Safe if not in state.
        from tools.aws.scope_shared.core.terra_runner import get_terra_env
        for res in ["aws_secretsmanager_secret.openai_api_key", "aws_secretsmanager_secret.db_password", "aws_secretsmanager_secret.db_password_plain"]:
            try:
                subprocess.run(
                    [os.getenv("FRU_TF_BIN", "tofu"), "state", "rm", res],
                    cwd=durable_dir,
                    env=get_terra_env(region),
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass
        aurora_pw = os.getenv("PGPASSWORD") or ""
        os.environ["TF_VAR_aurora_master_password"] = aurora_pw or "postgres"
        azs = get_azs(region)
        public_cidrs, private_cidrs = get_subnet_cidrs(region)
        azs_json = json.dumps(azs)
        public_json = json.dumps(public_cidrs)
        private_json = json.dumps(private_cidrs)
        os.environ["TF_VAR_azs"] = azs_json
        os.environ["TF_VAR_public_subnet_cidrs"] = public_json
        os.environ["TF_VAR_private_subnet_cidrs"] = private_json
        os.environ["TF_VAR_allow_destroy_durable"] = "false"
        durable_vars = [
            "-var", f"azs={azs_json}",
            "-var", f"public_subnet_cidrs={public_json}",
            "-var", f"private_subnet_cidrs={private_json}",
            "-var", "allow_destroy_durable=false",
        ]
        if aurora_pw:
            durable_vars += ["-var", f"aurora_master_password={aurora_pw}"]
        else:
            logger.warning("PGPASSWORD not set; Aurora creation may fail. Set in .env before deploy.")
            durable_vars += ["-var", "aurora_master_password=postgres"]
        with stats.timed("Tofu apply", "infra_terraform/live_deploy/aws/scope_shared/durable"):
            apply_stack(durable_dir, env, durable_vars, region)
        logger.success("Shared durable applied")
        tracker.end_phase(4)

        # Phase 5: Shared nondurable
        tracker.start_phase(5)
        logger.step(f"[5/{len(phases)}] Applying shared nondurable stack (ECR + S3)...")
        with stats.timed("Tofu apply", "infra_terraform/live_deploy/aws/scope_shared/nondurable"):
            apply_stack("infra_terraform/live_deploy/aws/scope_shared/nondurable", env, [], region)
        logger.success("Shared nondurable applied")
        tracker.end_phase(5)

        # Phase 6: Secrets
        tracker.start_phase(6)
        logger.step(f"[6/{len(phases)}] Ensuring secrets in Secrets Manager...")
        with stats.timed("Secrets", "ensure_secrets"):
            subprocess.run(
                ["python", "tools/aws/scope_shared/deploy/ensure_secrets.py", "--env", env, "--region", region],
                check=True,
                env={**os.environ, "CLOUD_REGION": region},
            )
        logger.success("Secrets ensured")
        tracker.end_phase(6)

        # Phase 7: Database setup
        tracker.start_phase(7)
        logger.step(f"[7/{len(phases)}] Setting up database (pgvector, schema, data)...")
        try:
            setup_db_cmd = ["python", "tools/aws/scope_shared/deploy/setup_database.py", "--env", env, "--region", region]
            if args.force_refresh_data:
                setup_db_cmd.append("--force-refresh-data")
            with stats.timed("Database", "setup_database"):
                subprocess.run(
                    setup_db_cmd,
                    check=True,
                    env={**os.environ, "CLOUD_REGION": region},
                )
            logger.success("Database setup complete")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Database setup had issues (may already be initialized): {e}")
        tracker.end_phase(7)

        # Phase 8: Build & push (skip if --skip-build or content-based skip)
        tracker.start_phase(8)
        content_skip = False
        # Content-based skip: hash build context (source + Dockerfile); if it matches
        # the hash stored in S3 from the last successful build, skip. Captures both
        # committed and uncommitted changes. --force-build bypasses this check.
        if not args.skip_build and not args.force_build:
            snd = tofu_output_json("infra_terraform/live_deploy/aws/scope_shared/nondurable", env, region)
            artifacts_bucket = snd.get("artifacts_bucket", {}).get("value", "")
            if artifacts_bucket:
                from tools.cloud_shared.docker.build_skip_decision import decide_build_skip

                app_key = f"build-metadata/{env}/app-build-hash.json"
                spark_key = f"build-metadata/{env}/spark-build-hash.json"
                skip_result = decide_build_skip(
                    force_build=False,
                    storage_bucket=artifacts_bucket,
                    app_key=app_key,
                    spark_key=spark_key,
                    provider="s3",
                    region=region,
                )
                if skip_result.skip:
                    content_skip = True
                    logger.step(f"[8/{len(phases)}] Skipping build (content hash matches); will use repo:latest from ECR")
                    logger.info(f"[BUILD] App hash {skip_result.app_hash[:8]}..., spark {skip_result.spark_hash[:8] if skip_result.spark_hash else 'n/a'}... match stored. Use --force-build to rebuild.")
                    if not os.getenv("APP_IMAGE_TAG"):
                        os.environ["APP_IMAGE_TAG"] = "latest"
                    if not os.getenv("SPARK_IMAGE_TAG"):
                        os.environ["SPARK_IMAGE_TAG"] = "latest"
                    _push_only_for_ecr_absence(env, region, snd)
                    tracker.end_phase(8)

        if args.skip_build:
            logger.step(f"[8/{len(phases)}] Skipping build (--skip-build); will use repo:latest from ECR")
            if not os.getenv("APP_IMAGE_TAG"):
                os.environ["APP_IMAGE_TAG"] = "latest"
            if not os.getenv("SPARK_IMAGE_TAG"):
                os.environ["SPARK_IMAGE_TAG"] = "latest"
            snd = tofu_output_json("infra_terraform/live_deploy/aws/scope_shared/nondurable", env, region)
            _push_only_for_ecr_absence(env, region, snd)
            tracker.end_phase(8)
        elif content_skip:
            pass  # Already ended phase 8 above
        else:
            logger.step(f"[8/{len(phases)}] Building and pushing images...")
            # Default SPARK_IMAGE_TAG when not in .env (e.g. commented out)
            if not os.getenv("SPARK_IMAGE_TAG"):
                os.environ["SPARK_IMAGE_TAG"] = "latest"
            # When APP_IMAGE_TAG is "latest" or unset, generate version tag and push both
            app_tag = os.getenv("APP_IMAGE_TAG", "latest")
            if app_tag == "latest":
                from tools.cloud_shared.image_tag import generate_image_tag, get_container_image_tags
                version_tag = generate_image_tag(env)
                os.environ["APP_IMAGE_TAG"] = version_tag
                os.environ["CONTAINER_IMAGE_TAGS"] = get_container_image_tags(version_tag)
                logger.info(f"[BUILD] Generated version tag: {version_tag} (will also push latest)")
            else:
                os.environ["CONTAINER_IMAGE_TAGS"] = app_tag
            build_env = {**os.environ, "CLOUD_REGION": region}
            build_env["PYTHONUNBUFFERED"] = "1"
            build_cmd = ["python", "tools/aws/scope_shared/deploy/build_and_push_images.py", "--env", env, "--region", region]
            if getattr(args, "no_cache", False) or args.force_spark_rebuild:
                build_cmd.append("--no-cache")
            if args.force_build:
                build_cmd.append("--force-build")
            with stats.timed("Build & push", "build_and_push_images"):
                proc = subprocess.run(build_cmd, cwd=os.getcwd(), env=build_env)
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, proc.args)
            logger.success("Images built and pushed")
            tracker.end_phase(8)

        # Phase 9: ECR URLs (and for --skip-build / content-skip: query ECR for latest image tags)
        tracker.start_phase(9)
        logger.step(f"[9/{len(phases)}] Getting ECR image URLs...")
        snd = tofu_output_json("infra_terraform/live_deploy/aws/scope_shared/nondurable", env, region)
        app_repo_url = snd["ecr_app_url"]["value"]
        spark_repo_url = snd["ecr_spark_url"]["value"]
        if args.skip_build or content_skip:
            app_image_full = f"{app_repo_url}:latest"
            spark_image_full = f"{spark_repo_url}:latest"
            # Query ECR for all tags on the image with tag=latest (for frontend display)
            repo_name = app_repo_url.split("/")[-1]
            try:
                out = subprocess.check_output(
                    [
                        "aws", "ecr", "describe-images",
                        "--repository-name", repo_name,
                        "--image-ids", "imageTag=latest",
                        "--region", region,
                        "--query", "imageDetails[0].imageTags",
                        "--output", "text",
                    ],
                    text=True,
                    timeout=15,
                )
                tags_str = out.strip().replace("\t", ",").replace(" ", ",")
                # Normalize: "tag1\ttag2" or "tag1 tag2" -> "tag1,tag2"
                tags_list = [t for t in tags_str.split(",") if t]
                if tags_list:
                    os.environ["CONTAINER_IMAGE_TAGS"] = ",".join(tags_list)
                    logger.info(f"[SKIP-BUILD] App image tags from ECR: {os.environ['CONTAINER_IMAGE_TAGS']}")
                else:
                    os.environ["CONTAINER_IMAGE_TAGS"] = "latest"
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.error(f"[SKIP-BUILD] Failed to get tags for repo:latest: {e}")
                logger.error("Ensure a full deploy has run at least once so 'latest' exists in ECR.")
                raise SystemExit(1)
        else:
            spark_image_full = f"{spark_repo_url}:{require('SPARK_IMAGE_TAG')}"
            app_image_full = f"{app_repo_url}:{require('APP_IMAGE_TAG')}"
        logger.info(f"App image: {app_image_full}")
        logger.info(f"Spark image: {spark_image_full}")
        logger.success("ECR URLs obtained")
        tracker.end_phase(9)

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
        logger.operation_end("Deploy", scope, env, region, int(time.time() - deploy_start), ok=True)
        sys.exit(0)

    except EnvVarNotFound as e:
        logger.error(str(e))
        logger.operation_end("Deploy", scope, env, region, int(time.time() - deploy_start), ok=False)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed at step: {e}")
        logger.operation_end("Deploy", scope, env, region, int(time.time() - deploy_start), ok=False)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deployment error: {e}")
        import traceback

        traceback.print_exc()
        logger.operation_end("Deploy", scope, env, region, int(time.time() - deploy_start), ok=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
