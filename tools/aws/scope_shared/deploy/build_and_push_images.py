"""
Build and push ECR images for app and spark.

Naming: regionless repo names (fru-api-img-dev, fru-spark-img-dev). Max 2 tags per image:
build-info (e.g. fru_dev_20260227_abc123) and latest. Enables push-only across regions.

Usage:
  python tools/aws/scope_shared/deploy/build_and_push_images.py --env dev
  python tools/aws/scope_shared/deploy/build_and_push_images.py --env dev --region us-west-2
  python tools/aws/scope_shared/deploy/build_and_push_images.py --env dev --region us-west-2 --push-only  # Push local image to target region (no build)

Flags:
  --env              Environment (default: FRU_ENV or dev)
  --region           Target region (default: CLOUD_REGION from .env)
  --no-cache         Build Spark image without Docker cache (ensures fresh run_analytics.py)
  --push-only        Skip build; tag canonical local images for target ECR and push
  --cleanup-local    Also remove current local images after push (optional; old images removed after successful build)
  --skip-cleanup     Skip post-push cleanup (default)
  --skip-untag-ecr   Keep ECR registry tags locally after push (default: remove them for cleaner local state)
  --force-build      Passthrough from deploy; no-op here

Typical flows:
  Full build:  build_and_push_images.py --env dev
  Multi-region push:  build_and_push_images.py --env dev --region us-west-2 --push-only

This tool:
- Reads ECR repository URLs from `infra_terraform/live_deploy/aws/scope_shared/nondurable` state
- Logs into ECR properly
- Builds and pushes images (or --push-only: tag local image for target ECR and push)
- After each push: removes ECR registry tags locally (e.g. 744139897900.dkr.ecr.us-east-2.amazonaws.com/fru-api-img-dev:latest),
  keeping only canonical names (fru-api-img-dev:latest). Local state differs from ECR by design—see _untag_ecr_refs_after_push.
- Removes old local images after successful build and push; use --cleanup-local to also remove current images
- Content-based skip: deploy.py checks build-context hash before calling this; when hash
  matches stored value in S3, deploy may skip build and call --push-only for regions missing the image.
  See docs/learned/cloud_shared/DEPLOY_BUILD_DOCKER.md for details.
"""
import argparse, os, json, subprocess, sys
from tools.cloud_shared.env import load_dotenv, require, get_int_env
from tools.aws.scope_shared.core.terra_runner import get_terra_env
from tools.aws.scope_shared.core.backend import backend_config, resolve_region
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.deploy.build_context_hash import (
    compute_build_context_hash,
    store_build_hash,
)
from tools.cloud_shared.docker.build_common import (
    run_docker_with_progress,
    sh,
    remove_old_local_images_after_build,
    untag_registry_refs_after_push,
    docker_basic_timeout,
    docker_hung_suggestion,
)

load_dotenv()


def tofu_output_json(stack_dir: str, env: str, region: str | None = None):
    logger.info(f"[TOFU OUTPUT] Getting outputs from {stack_dir}")
    try:
        cfg = backend_config(stack_dir, env, region)
        args = ["init","-upgrade","-reconfigure"]
        for c in cfg:
            args += ["-backend-config", c]
        subprocess.run([os.getenv("FRU_TF_BIN","tofu")] + args, cwd=stack_dir, check=True, env=get_terra_env(region))
        out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd=stack_dir, text=True, timeout=30, env=get_terra_env(region))
        result = json.loads(out)
        logger.success(f"[TOFU OUTPUT OK] {stack_dir}")
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"[TOFU OUTPUT TIMEOUT] {stack_dir}")
        raise SystemExit(f"Tofu output timed out for {stack_dir}")
    except Exception as e:
        logger.error(f"[TOFU OUTPUT ERROR] {stack_dir}: {e}")
        raise

def _ecr_image_exists(repo_name: str, tag: str, region: str) -> bool:
    """Check if image exists in ECR. Used for safety checks and push-only skip."""
    try:
        subprocess.check_output(
            [
                "aws", "ecr", "describe-images",
                "--repository-name", repo_name,
                "--image-ids", f"imageTag={tag}",
                "--region", region,
            ],
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _run_push_only(
    target_app_url: str,
    target_spark_url: str,
    target_region: str,
    env: str,
    artifacts_bucket: str,
    skip_untag_ecr: bool = False,
) -> None:
    """
    Push-only mode: tag local images (repo_name:latest) for target ECR and push.
    Skips if target ECR already has both images. Repo name is regionless (fru-api-img-dev),
    so same local tag works for any region—just re-tag for target registry. See docs/learned/cloud_shared/DEPLOY_BUILD_DOCKER.md.
    After push: removes ECR registry tags locally (unless skip_untag_ecr) so only canonical names remain.
    """
    app_repo_name = target_app_url.split("/")[-1]
    spark_repo_name = target_spark_url.split("/")[-1]

    # Skip if target already has both images
    if _ecr_image_exists(app_repo_name, "latest", target_region) and _ecr_image_exists(spark_repo_name, "latest", target_region):
        logger.info("[PUSH-ONLY] Target ECR already has app and spark images; skipping push")
        return

    registry = target_app_url.split("/")[0]
    # Safety: ECR URL format is {account}.dkr.ecr.{region}.amazonaws.com
    if f".dkr.ecr.{target_region}." not in target_app_url:
        logger.error(f"[PUSH-ONLY] Registry mismatch: target_region={target_region} but URL={target_app_url}")
        raise SystemExit(1)
    logger.info(f"[PUSH-ONLY] Pushing to registry {registry} (target region: {target_region})")
    ecr_login(registry, target_region)

    # Tag canonical (regionless) local images -> target ECR and push
    need_app = not _ecr_image_exists(app_repo_name, "latest", target_region)
    need_spark = not _ecr_image_exists(spark_repo_name, "latest", target_region)

    if need_app:
        sh(["docker", "tag", f"{app_repo_name}:latest", f"{target_app_url}:latest"])
        sh(["docker", "push", f"{target_app_url}:latest"])
        logger.success(f"[PUSH-ONLY] Pushed app image to ECR {target_region}; left {app_repo_name}:latest locally")
    if need_spark:
        sh(["docker", "tag", f"{spark_repo_name}:latest", f"{target_spark_url}:latest"])
        sh(["docker", "push", f"{target_spark_url}:latest"])
        logger.success(f"[PUSH-ONLY] Pushed spark image to ECR {target_region}; left {spark_repo_name}:latest locally")

    # Remove ECR registry tags locally so only canonical names remain (see _untag_ecr_refs_after_push)
    if (need_app or need_spark) and not skip_untag_ecr:
        untag_registry_refs_after_push(
            target_app_url, target_spark_url, "latest", "latest"
        )

    # Store build hash for target region so future content-skip works
    if artifacts_bucket:
        app_hash = compute_build_context_hash("core_app", "Dockerfile")
        tools_hash = compute_build_context_hash("tools/cloud_shared", "")
        app_hash_combined = f"{app_hash}_{tools_hash[:12]}" if tools_hash else app_hash
        spark_hash = compute_build_context_hash("core_app", "analytics/docker/Dockerfile")
        app_key = f"build-metadata/{env}/app-build-hash.json"
        spark_key = f"build-metadata/{env}/spark-build-hash.json"
        try:
            store_build_hash(artifacts_bucket, app_key, target_region, app_hash_combined, "latest")
            store_build_hash(artifacts_bucket, spark_key, target_region, spark_hash, "latest")
            logger.info("[PUSH-ONLY] Stored build hashes for target region")
        except subprocess.CalledProcessError as e:
            logger.warning(f"[PUSH-ONLY] Could not store hashes: {e}")


def _cleanup_local_images_after_push(
    app_repo_url: str,
    spark_repo_url: str,
    app_tag: str,
    spark_tag: str,
    region: str,
) -> None:
    """
    Remove local Docker images after successful ECR push (opt-in via --cleanup-local).
    Verifies each image exists in ECR before removal. Non-fatal: errors are warnings.
    Max 2 tags per image: build-info + latest. Dedupe refs in case tag==latest.
    """
    app_repo_name = app_repo_url.split("/")[-1]
    spark_repo_name = spark_repo_url.split("/")[-1]

    # All refs we may have created. Set dedupes when app_tag==latest etc.
    images_to_remove: list[str] = list({
        f"{app_repo_name}:{app_tag}", f"{app_repo_name}:latest",
        f"{app_repo_url}:{app_tag}", f"{app_repo_url}:latest",
        f"{spark_repo_name}:{spark_tag}", f"{spark_repo_name}:latest",
        f"{spark_repo_url}:{spark_tag}", f"{spark_repo_url}:latest",
    })

    logger.info("[CLEANUP] Verifying images in ECR before local removal...")
    if not _ecr_image_exists(app_repo_name, app_tag, region):
        logger.warning("[CLEANUP] App image not found in ECR - skipping local cleanup for safety")
        return
    if app_tag != "latest" and not _ecr_image_exists(app_repo_name, "latest", region):
        logger.warning("[CLEANUP] App:latest not found in ECR - skipping local cleanup for safety")
        return
    if not _ecr_image_exists(spark_repo_name, spark_tag, region):
        logger.warning("[CLEANUP] Spark image not found in ECR - skipping local cleanup for safety")
        return

    logger.success("[CLEANUP] ECR images verified, removing local copies...")
    removed = 0
    for image_ref in images_to_remove:
        try:
            result = subprocess.run(
                ["docker", "rmi", "-f", image_ref],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                removed += 1
                logger.success(f"  ✓ Removed: {image_ref}")
            else:
                logger.warning(f"  ✗ Could not remove {image_ref} (may be in use)")
        except subprocess.TimeoutExpired:
            logger.warning(f"  ✗ Timeout removing {image_ref}")
        except Exception as e:
            logger.warning(f"  ✗ Could not remove {image_ref}: {e}")

    if removed > 0:
        logger.success(f"[CLEANUP] Local images removed ({removed})")


def ecr_login(registry: str, region: str):
    """Log in to ECR via aws ecr get-login-password | docker login. Uses ~/.docker/config.json."""
    logger.info(f"[ECR LOGIN] Logging in to {registry}")
    timeout = docker_basic_timeout()
    try:
        pw = subprocess.check_output(["aws","ecr","get-login-password","--region",region], text=True, timeout=10)
        logger.info(f"[RUN] docker login --username AWS --password-stdin {registry}")
        subprocess.run(
            ["docker","login","--username","AWS","--password-stdin",registry],
            input=pw,
            text=True,
            check=True,
            timeout=timeout,
        )
        logger.success("[ECR LOGIN OK]")
    except subprocess.TimeoutExpired as e:
        logger.error(f"[ECR LOGIN TIMEOUT] docker login did not complete within {e.timeout}s")
        logger.error("This usually means the Docker daemon is hung or unresponsive.")
        logger.error(docker_hung_suggestion())
        raise SystemExit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"[ECR LOGIN FAILED] {e}")
        raise
    except Exception as e:
        logger.error(f"[ECR LOGIN ERROR] {e}")
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--no-cache", action="store_true", help="Build Spark image without cache (ensures fresh run_analytics.py)")
    ap.add_argument("--skip-cleanup", action="store_true", help="Skip local image removal after push (default: skip, keep for multi-region)")
    ap.add_argument("--cleanup-local", action="store_true", help="Remove local images after push (opt-in; default is keep for multi-region push)")
    ap.add_argument("--skip-untag-ecr", action="store_true", help="Keep ECR registry tags locally after push (default: remove for cleaner local state)")
    ap.add_argument("--force-build", action="store_true", help="Force build (passed by deploy when user requests; no-op here)")
    ap.add_argument("--push-only", action="store_true", help="Skip build; tag canonical local images (repo_name:latest) for target ECR and push.")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    logger.step("Building and pushing Docker images" if not args.push_only else "Push-only (no build)")
    logger.info(f"[BUILD] Region: {region}")

    logger.info("[BUILD] Getting ECR URLs from terraform state...")
    out = tofu_output_json("infra_terraform/live_deploy/aws/scope_shared/nondurable", args.env, region)

    if "ecr_app_url" not in out or "ecr_spark_url" not in out:
        logger.error("[BUILD] nondurable stack has no ecr_app_url/ecr_spark_url outputs.")
        logger.error("Run deploy first so nondurable is applied (creates ECR repos). Or run: python tools/aws/deploy.py --scope all --env dev")
        raise SystemExit(1)
    app_repo_url   = out["ecr_app_url"]["value"]
    spark_repo_url = out["ecr_spark_url"]["value"]
    artifacts_bucket = out.get("artifacts_bucket", {}).get("value", "")

    logger.info(f"[BUILD] App repo: {app_repo_url}")
    logger.info(f"[BUILD] Spark repo: {spark_repo_url}")

    if args.push_only:
        # Push-only: tag canonical local images (repo_name:latest) for target ECR and push.
        # Used when content-skip but target region ECR is empty (e.g. deploy us-west-2 after us-east-1).
        _run_push_only(
            app_repo_url, spark_repo_url, region, args.env, artifacts_bucket,
            skip_untag_ecr=args.skip_untag_ecr,
        )
        sys.exit(0)

    app_tag = require("APP_IMAGE_TAG")
    spark_tag = require("SPARK_IMAGE_TAG")
    platform = os.getenv("DOCKER_RUN_REMOTE_PLATFORM", "linux/amd64")

    logger.info(f"[BUILD] Platform: {platform}")
    logger.info(f"[BUILD] App tag: {app_tag}")
    logger.info(f"[BUILD] Spark tag: {spark_tag}")

    registry = app_repo_url.split("/")[0]
    
    logger.info("[BUILD] Logging in to ECR...")
    ecr_login(registry, region)

    # Repo name is regionless (fru-api-img-dev). Same name in all regions for push-only.
    app_repo_name = app_repo_url.split("/")[-1]
    spark_repo_name = spark_repo_url.split("/")[-1]

    # Content-based skip: compute hash of build context (source files + Dockerfile).
    # Stored as image label and in S3 after push. Deploy uses this to skip build
    # on future runs when nothing changed. Captures both committed and uncommitted
    # changes—local edits before commit will trigger rebuild.
    app_hash = compute_build_context_hash("core_app", "Dockerfile")
    tools_hash = compute_build_context_hash("tools/cloud_shared", "")
    app_hash_combined = f"{app_hash}_{tools_hash[:12]}" if tools_hash else app_hash
    spark_hash = compute_build_context_hash("core_app", "analytics/docker/Dockerfile")

    # Build with local tags only (max 2 per image: build-info + latest). Push tags to ECR.
    # --progress=plain: line-by-line output; avoids silent buffering in Cursor/CI.
    # --build-arg BUILD_CONTEXT_HASH: stored as image label for traceability.
    app_build_cmd = ["docker", "build", "--progress=plain", "--platform", platform,
         "--build-arg", f"BUILD_CONTEXT_HASH={app_hash_combined}",
         "-t", f"{app_repo_name}:{app_tag}", "-f", "core_app/Dockerfile", "."]
    if args.no_cache:
        app_build_cmd.insert(2, "--no-cache")
        logger.info("[BUILD] App: --no-cache (cache-free)")
    run_docker_with_progress(app_build_cmd, "Building app image", 1, 4)
    spark_build_cmd = ["docker", "build", "--progress=plain", "--platform", platform,
         "--build-arg", f"BUILD_CONTEXT_HASH={spark_hash}",
         "-t", f"{spark_repo_name}:{spark_tag}", "-f", "core_app/analytics/docker/Dockerfile", "core_app"]
    if args.no_cache:
        spark_build_cmd.insert(2, "--no-cache")
        logger.info("[BUILD] Spark: --no-cache (cache-free)")
    run_docker_with_progress(
        spark_build_cmd,
        "Building spark image", 2, 4,
    )

    # Tag latest for same image (max 2 tags: build-info + latest).
    if app_tag != "latest":
        sh(["docker", "tag", f"{app_repo_name}:{app_tag}", f"{app_repo_name}:latest"])
    if spark_tag != "latest":
        sh(["docker", "tag", f"{spark_repo_name}:{spark_tag}", f"{spark_repo_name}:latest"])

    # Push: tag for target ECR (registry from tofu output) and push. Same repo name in all regions.
    total_steps = 4 + (1 if app_tag != "latest" else 0) + (1 if spark_tag != "latest" else 0)
    step = 3
    sh(["docker", "tag", f"{app_repo_name}:{app_tag}", f"{app_repo_url}:{app_tag}"])
    run_docker_with_progress(
        ["docker","push",f"{app_repo_url}:{app_tag}"],
        "Pushing app image", step, total_steps,
    )
    step += 1
    if app_tag != "latest":
        sh(["docker", "tag", f"{app_repo_name}:latest", f"{app_repo_url}:latest"])
        run_docker_with_progress(
            ["docker","push",f"{app_repo_url}:latest"],
            "Pushing app image (latest)", step, total_steps,
        )
        step += 1
    sh(["docker", "tag", f"{spark_repo_name}:{spark_tag}", f"{spark_repo_url}:{spark_tag}"])
    run_docker_with_progress(
        ["docker", "push", f"{spark_repo_url}:{spark_tag}"],
        "Pushing spark image", step, total_steps,
    )
    step += 1
    if spark_tag != "latest":
        sh(["docker", "tag", f"{spark_repo_name}:latest", f"{spark_repo_url}:latest"])
        try:
            run_docker_with_progress(
                ["docker", "push", f"{spark_repo_url}:latest"],
                "Pushing spark image (latest)", step, total_steps,
            )
        except subprocess.CalledProcessError as e:
            msg = str(e)
            # On some Docker / ECR combinations, pushing an existing manifest
            # tagged as :latest can fail with a "does not provide any platform"
            # message even though the versioned tag push succeeded. This tag is
            # only a convenience alias, so we treat that specific error as a
            # non-fatal warning and continue with deploy.
            if "does not provide any platform" in msg:
                logger.warning(
                    "[BUILD] Ignoring non-fatal spark :latest push error "
                    "(image manifest without platform info). "
                    "Deploy will use the versioned SPARK_IMAGE_TAG instead."
                )
            else:
                raise

    # Store build-context hashes to S3 so deploy can skip build on future runs
    # when compute_build_context_hash() matches. Path: build-metadata/{env}/*.json
    if artifacts_bucket:
        app_key = f"build-metadata/{args.env}/app-build-hash.json"
        spark_key = f"build-metadata/{args.env}/spark-build-hash.json"
        try:
            store_build_hash(artifacts_bucket, app_key, region, app_hash_combined, app_tag)
            store_build_hash(artifacts_bucket, spark_key, region, spark_hash, spark_tag)
            logger.info(f"[BUILD] Stored build-context hashes for content-based skip (app={app_hash_combined[:8]}..., spark={spark_hash[:8]}...)")
        except subprocess.CalledProcessError as e:
            logger.warning(f"[BUILD] Could not store build hashes to S3 (non-fatal): {e}")

    logger.success("All images pushed to ECR:")
    print("  ", f"{app_repo_url}:{app_tag}")
    print("  ", f"{spark_repo_url}:{spark_tag}")

    # Remove ECR registry tags locally so only canonical names remain (fru-api-img-dev, fru-spark-img-dev).
    # Local state intentionally differs from ECR—see _untag_ecr_refs_after_push docstring.
    if not args.skip_untag_ecr:
        untag_registry_refs_after_push(app_repo_url, spark_repo_url, app_tag, spark_tag)
        logger.info(f"[BUILD] Local refs kept: {app_repo_name}:latest, {spark_repo_name}:latest")

    # Remove old local images only after new images are successfully built and pushed
    remove_old_local_images_after_build()

    if args.cleanup_local and not args.skip_cleanup:
        _cleanup_local_images_after_push(
            app_repo_url, spark_repo_url, app_tag, spark_tag, region
        )

    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as e:
        logger.error(f"Build step timed out after {e.timeout}s: {e.cmd}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Build and push failed: {e}")
        sys.exit(1)
