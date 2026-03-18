"""
Build and push Artifact Registry images for app and spark (GCP).

Usage:
  python tools/gcp/scope_shared/deploy/build_and_push_images.py --env dev
  python tools/gcp/scope_shared/deploy/build_and_push_images.py --env dev --region us-central1
  python tools/gcp/scope_shared/deploy/build_and_push_images.py --env dev --push-only --region us-central1
"""
import argparse
import json
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv, get_int_env
from tools.cloud_shared.logging import logger
from tools.cloud_shared.docker.build_common import (
    run_docker_with_progress,
    sh,
    remove_old_local_images_after_build,
    untag_registry_refs_after_push,
    docker_basic_timeout,
    docker_hung_suggestion,
)
from tools.cloud_shared.docker.build_context_hash import (
    compute_build_context_hash,
    get_stored_build_hash,
    store_build_hash,
)

load_dotenv()


def tofu_output_json(stack_dir: str, env: str, region: str | None = None):
    logger.info(f"[TOFU OUTPUT] Getting outputs from {stack_dir}")
    from tools.gcp.scope_shared.core.backend import backend_config
    from tools.gcp.scope_shared.core.terra_runner import get_terra_env

    try:
        cfg = backend_config(stack_dir, env, region, cloud="gcp")
        args = ["init", "-upgrade", "-reconfigure"]
        for c in cfg:
            args += ["-backend-config", c]
        subprocess.run(
            [os.getenv("FRU_TF_BIN", "tofu")] + args,
            cwd=stack_dir,
            check=True,
            env=get_terra_env(region),
        )
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=stack_dir,
            text=True,
            timeout=30,
            env=get_terra_env(region),
        )
        result = json.loads(out)
        logger.success(f"[TOFU OUTPUT OK] {stack_dir}")
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"[TOFU OUTPUT TIMEOUT] {stack_dir}")
        raise SystemExit(f"Tofu output timed out for {stack_dir}")
    except Exception as e:
        logger.error(f"[TOFU OUTPUT ERROR] {stack_dir}: {e}")
        raise


def _artifact_registry_login(registry_host: str) -> None:
    """Configure Docker to authenticate with Artifact Registry."""
    logger.info(f"[AR LOGIN] Configuring Docker for {registry_host}")
    timeout = docker_basic_timeout()
    try:
        subprocess.run(
            ["gcloud", "auth", "configure-docker", registry_host, "--quiet"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        logger.success("[AR LOGIN OK]")
    except subprocess.TimeoutExpired as e:
        logger.error(f"[AR LOGIN TIMEOUT] {e}")
        logger.error(docker_hung_suggestion())
        raise SystemExit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"[AR LOGIN FAILED] {e}")
        raise


def _artifact_registry_image_exists(registry_url: str, tag: str) -> bool:
    """Check if image:tag exists in Artifact Registry."""
    try:
        out = subprocess.check_output(
            ["gcloud", "artifacts", "docker", "tags", "list", f"{registry_url}"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return tag in out
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--no-cache", action="store_true", help="Build app and Spark images without Docker cache")
    ap.add_argument("--skip-untag-ecr", action="store_true", help="Keep registry tags locally after push")
    ap.add_argument("--skip-untag", action="store_true", dest="skip_untag_ecr", help="Alias for --skip-untag-ecr")
    ap.add_argument("--force-build", action="store_true", help="Force build (no-op)")
    ap.add_argument("--push-only", action="store_true", help="Skip build; tag and push local images")
    args = ap.parse_args()

    from tools.gcp.scope_shared.core.backend import resolve_region
    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    logger.step("Building and pushing Docker images" if not args.push_only else "Push-only (no build)")
    logger.info(f"[BUILD] Region: {region}")

    logger.info("[BUILD] Getting Artifact Registry URLs from terraform state...")
    out = tofu_output_json("infra_terraform/live_deploy/gcp/scope_shared/nondurable", args.env, region)

    app_repo_url = out.get("artifact_registry_app_url", {}).get("value", "")
    spark_repo_url = out.get("artifact_registry_spark_url", {}).get("value", "")
    delta_bucket = out.get("delta_bucket_name", {}).get("value", "")

    if not app_repo_url or not spark_repo_url:
        logger.error("[BUILD] nondurable stack has no artifact_registry_app_url/artifact_registry_spark_url outputs.")
        logger.error("Run deploy first so nondurable is applied. Or: python tools/gcp/deploy.py --scope all --env dev")
        raise SystemExit(1)

    # Canonical local names (like AWS): fru-api-img-gcp-dev, fru-spark-img-gcp-dev, fru-kube-proxy-img-gcp-dev
    from tools.gcp.scope_shared.core.resource_names import artifact_registry_repo_app, artifact_registry_repo_spark
    app_repo_name = artifact_registry_repo_app(args.env)
    spark_repo_name = artifact_registry_repo_spark(args.env)
    kube_proxy_repo_name = f"fru-kube-proxy-img-gcp-{args.env}"

    # Artifact Registry format: REGISTRY/PROJECT/REPOSITORY/IMAGE:TAG (IMAGE required)
    # kube-proxy uses app repo (same registry) for GCP kube Cloud Run proxy
    _APP_IMAGE_NAME = "app"
    _SPARK_IMAGE_NAME = "spark"
    _KUBE_PROXY_IMAGE_NAME = "kube-proxy"
    app_image_url = f"{app_repo_url}/{_APP_IMAGE_NAME}"
    spark_image_url = f"{spark_repo_url}/{_SPARK_IMAGE_NAME}"
    kube_proxy_image_url = f"{app_repo_url}/{_KUBE_PROXY_IMAGE_NAME}"

    # Validate URL format (no duplicate project in path)
    if app_repo_url.count("fru-proj-1") > 1 or spark_repo_url.count("fru-proj-1") > 1:
        logger.warning("[BUILD] Artifact Registry URL may have duplicate project; check Terraform outputs")

    logger.info(f"[BUILD] App repo: {app_repo_url} (local: {app_repo_name})")
    logger.info(f"[BUILD] Spark repo: {spark_repo_url} (local: {spark_repo_name})")

    registry_host = app_repo_url.split("/")[0]
    _artifact_registry_login(registry_host)

    if args.push_only:
        has_all = (
            _artifact_registry_image_exists(app_image_url, "latest")
            and _artifact_registry_image_exists(spark_image_url, "latest")
            and _artifact_registry_image_exists(kube_proxy_image_url, "latest")
        )
        if has_all:
            logger.info("[PUSH-ONLY] Target Artifact Registry already has app, spark, and kube-proxy; skipping push")
            sys.exit(0)
        need_app = not _artifact_registry_image_exists(app_image_url, "latest")
        need_spark = not _artifact_registry_image_exists(spark_image_url, "latest")
        need_kube_proxy = not _artifact_registry_image_exists(kube_proxy_image_url, "latest")
        if need_app:
            sh(["docker", "tag", f"{app_repo_name}:latest", f"{app_image_url}:latest"])
            sh(["docker", "push", f"{app_image_url}:latest"])
            logger.success(f"[PUSH-ONLY] Pushed app image to Artifact Registry")
        if need_spark:
            sh(["docker", "tag", f"{spark_repo_name}:latest", f"{spark_image_url}:latest"])
            sh(["docker", "push", f"{spark_image_url}:latest"])
            logger.success(f"[PUSH-ONLY] Pushed spark image to Artifact Registry")
        if need_kube_proxy:
            sh(["docker", "tag", f"{kube_proxy_repo_name}:latest", f"{kube_proxy_image_url}:latest"])
            sh(["docker", "push", f"{kube_proxy_image_url}:latest"])
            logger.success(f"[PUSH-ONLY] Pushed kube-proxy image to Artifact Registry")
        if (need_app or need_spark or need_kube_proxy) and not args.skip_untag_ecr:
            untag_registry_refs_after_push(
                app_image_url, spark_image_url, "latest", "latest",
                app_canonical_name=app_repo_name, spark_canonical_name=spark_repo_name,
            )
        if delta_bucket:
            app_hash = compute_build_context_hash("core_app", "Dockerfile")
            tools_hash = compute_build_context_hash("tools/cloud_shared", "")
            app_hash_combined = f"{app_hash}_{tools_hash[:12]}" if tools_hash else app_hash
            spark_hash = compute_build_context_hash("core_app", "analytics/docker/Dockerfile")
            app_key = f"build-metadata/{args.env}/app-build-hash.json"
            spark_key = f"build-metadata/{args.env}/spark-build-hash.json"
            try:
                store_build_hash(delta_bucket, app_key, "gcs", app_hash_combined, "latest")
                store_build_hash(delta_bucket, spark_key, "gcs", spark_hash, "latest")
                logger.info("[PUSH-ONLY] Stored build hashes for target region")
            except subprocess.CalledProcessError as e:
                logger.warning(f"[PUSH-ONLY] Could not store hashes: {e}")
        sys.exit(0)

    app_tag = (os.getenv("APP_IMAGE_TAG") or "").strip() or "latest"
    spark_tag = (os.getenv("SPARK_IMAGE_TAG") or "").strip() or "latest"
    platform = os.getenv("DOCKER_RUN_REMOTE_PLATFORM", "linux/amd64")

    logger.info(f"[BUILD] Platform: {platform}")
    logger.info(f"[BUILD] App tag: {app_tag}")
    logger.info(f"[BUILD] Spark tag: {spark_tag}")

    app_hash = compute_build_context_hash("core_app", "Dockerfile")
    tools_hash = compute_build_context_hash("tools/cloud_shared", "")
    app_hash_combined = f"{app_hash}_{tools_hash[:12]}" if tools_hash else app_hash
    spark_hash = compute_build_context_hash("core_app", "analytics/docker/Dockerfile")

    app_build_cmd = ["docker", "build", "--progress=plain", "--platform", platform,
         "--build-arg", f"BUILD_CONTEXT_HASH={app_hash_combined}",
         "-t", f"{app_repo_name}:{app_tag}", "-f", "core_app/Dockerfile", "."]
    if args.no_cache:
        app_build_cmd.insert(2, "--no-cache")
        logger.info("[BUILD] App: --no-cache (fresh build)")
    run_docker_with_progress(app_build_cmd, "Building app image", 1, 5)
    spark_build_cmd = ["docker", "build", "--progress=plain", "--platform", platform,
         "--build-arg", f"BUILD_CONTEXT_HASH={spark_hash}",
         "-t", f"{spark_repo_name}:{spark_tag}", "-f", "core_app/analytics/docker/Dockerfile", "core_app"]
    if args.no_cache:
        spark_build_cmd.insert(2, "--no-cache")
        logger.info("[BUILD] Spark: --no-cache (fresh build)")
    run_docker_with_progress(spark_build_cmd, "Building spark image", 2, 5)
    kube_proxy_hash = compute_build_context_hash("core_app/kube_proxy", "Dockerfile")
    kube_proxy_build_cmd = ["docker", "build", "--progress=plain", "--platform", platform,
         "--build-arg", f"BUILD_CONTEXT_HASH={kube_proxy_hash}",
         "-t", f"{kube_proxy_repo_name}:{app_tag}", "-f", "core_app/kube_proxy/Dockerfile", "core_app/kube_proxy"]
    if args.no_cache:
        kube_proxy_build_cmd.insert(2, "--no-cache")
    run_docker_with_progress(kube_proxy_build_cmd, "Building kube-proxy image", 3, 5)

    if app_tag != "latest":
        sh(["docker", "tag", f"{app_repo_name}:{app_tag}", f"{app_repo_name}:latest"])
    if spark_tag != "latest":
        sh(["docker", "tag", f"{spark_repo_name}:{spark_tag}", f"{spark_repo_name}:latest"])
    if app_tag != "latest":
        sh(["docker", "tag", f"{kube_proxy_repo_name}:{app_tag}", f"{kube_proxy_repo_name}:latest"])

    step = 3
    sh(["docker", "tag", f"{app_repo_name}:{app_tag}", f"{app_image_url}:{app_tag}"])
    run_docker_with_progress(
        ["docker", "push", f"{app_image_url}:{app_tag}"],
        "Pushing app image", step, 4,
    )
    step += 1
    if app_tag != "latest":
        sh(["docker", "tag", f"{app_repo_name}:latest", f"{app_image_url}:latest"])
        run_docker_with_progress(
            ["docker", "push", f"{app_image_url}:latest"],
            "Pushing app image (latest)", step, 5,
        )
        step += 1
    sh(["docker", "tag", f"{spark_repo_name}:{spark_tag}", f"{spark_image_url}:{spark_tag}"])
    run_docker_with_progress(
        ["docker", "push", f"{spark_image_url}:{spark_tag}"],
        "Pushing spark image", step, 5,
    )
    if spark_tag != "latest":
        sh(["docker", "tag", f"{spark_repo_name}:latest", f"{spark_image_url}:latest"])
        try:
            run_docker_with_progress(
                ["docker", "push", f"{spark_image_url}:latest"],
                "Pushing spark image (latest)", step + 1, 6,
            )
        except subprocess.CalledProcessError as e:
            msg = str(e)
            # On some Docker / Artifact Registry combinations, pushing a manifest
            # tagged as :latest can fail with "does not provide any platform" even
            # though the versioned tag push succeeded. :latest is a convenience
            # alias; deploy uses SPARK_IMAGE_TAG, so treat this as non-fatal.
            if "does not provide any platform" in msg:
                logger.warning(
                    "[BUILD] Ignoring non-fatal spark :latest push error "
                    "(image manifest without platform info). "
                    "Deploy will use the versioned SPARK_IMAGE_TAG instead."
                )
            else:
                raise
        step += 1
    # kube-proxy: GCP kube Cloud Run proxy (HTTPS + *.run.app)
    sh(["docker", "tag", f"{kube_proxy_repo_name}:{app_tag}", f"{kube_proxy_image_url}:{app_tag}"])
    run_docker_with_progress(
        ["docker", "push", f"{kube_proxy_image_url}:{app_tag}"],
        "Pushing kube-proxy image", step + 1, 6,
    )
    if app_tag != "latest":
        sh(["docker", "tag", f"{kube_proxy_repo_name}:latest", f"{kube_proxy_image_url}:latest"])
        run_docker_with_progress(
            ["docker", "push", f"{kube_proxy_image_url}:latest"],
            "Pushing kube-proxy image (latest)", step + 2, 6,
        )

    if delta_bucket:
        app_key = f"build-metadata/{args.env}/app-build-hash.json"
        spark_key = f"build-metadata/{args.env}/spark-build-hash.json"
        try:
            store_build_hash(delta_bucket, app_key, "gcs", app_hash_combined, app_tag)
            store_build_hash(delta_bucket, spark_key, "gcs", spark_hash, spark_tag)
            logger.info(f"[BUILD] Stored build-context hashes (app={app_hash_combined[:8]}..., spark={spark_hash[:8]}...)")
        except subprocess.CalledProcessError as e:
            logger.warning(f"[BUILD] Could not store build hashes to GCS (non-fatal): {e}")

    logger.success("All images pushed to Artifact Registry:")
    print("  ", f"{app_image_url}:{app_tag}")
    print("  ", f"{spark_image_url}:{spark_tag}")
    print("  ", f"{kube_proxy_image_url}:{app_tag}")

    if not args.skip_untag_ecr:
        untag_registry_refs_after_push(
            app_image_url, spark_image_url, app_tag, spark_tag,
            app_canonical_name=app_repo_name, spark_canonical_name=spark_repo_name,
        )

    remove_old_local_images_after_build()
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
