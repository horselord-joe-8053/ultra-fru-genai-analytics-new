"""
Deploy image tag resolution and URI construction. Shared by AWS, GCP, Local.

Single source of truth: deploy sets APP_IMAGE_TAG; scope deployers call get_deploy_image_uris()
to obtain full image URIs. Never use "latest" for deploy; resolve from registry when needed.

Tag lookup delegates to tools.cloud_shared.image_registry_tags (DRY).
"""
import json
import os
import subprocess
from typing import Any

from tools.cloud_shared.image_registry_tags import get_image_tags

__all__ = [
    "resolve_app_tag",
    "resolve_spark_tag",
    "registry_has_required_images",
    "get_deploy_image_uris",
]


def _gcp_artifact_registry_has_image(registry_url: str, tag: str = "latest") -> bool:
    """Return True if Artifact Registry has the given image:tag."""
    try:
        out = subprocess.check_output(
            ["gcloud", "artifacts", "docker", "tags", "list", registry_url],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return tag in out
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _resolve_version_tag_from_registry(
    container_image: str, provider: str, region: str
) -> str:
    """
    Use get_image_tags to fetch all tags; return first non-latest (version tag).
    Raises if no version tag found.
    """
    tags = get_image_tags(container_image, provider, region)
    for t in tags:
        if t and t != "latest":
            return t
    raise ValueError(
        f"No version tag found for {container_image} (only 'latest' or empty). "
        "Run full deploy without --skip-build first."
    )


def resolve_app_tag(
    provider: str,
    env: str,
    region: str,
    app_image_url: str,
    *,
    app_repo_name: str | None = None,
) -> str:
    """
    Resolve app image tag: use APP_IMAGE_TAG from env if set and not "latest";
    else query registry (via get_image_tags) for what "latest" points to and return version tag.

    Args:
        provider: "gcp" | "aws" | "local"
        env: Environment (e.g. "dev")
        region: Region (e.g. "us-central1", "us-east-1")
        app_image_url: Full image URL (e.g. region-docker.pkg.dev/proj/repo/app or ECR URL)
        app_repo_name: Unused; kept for backward compatibility.
    """
    tag = (os.getenv("APP_IMAGE_TAG") or "").strip()
    if tag and tag != "latest":
        return tag

    if provider == "local":
        return "local"

    # Query registry for tags on image:latest; pick first non-latest
    container_image = f"{app_image_url.rstrip('/')}:latest"
    return _resolve_version_tag_from_registry(container_image, provider, region)


def resolve_spark_tag(
    provider: str,
    env: str,
    region: str,
    spark_image_url: str,
    *,
    app_image_url: str | None = None,
    app_repo_name: str | None = None,
) -> str:
    """Same as app; spark uses same tag as app."""
    if app_image_url:
        return resolve_app_tag(provider, env, region, app_image_url, app_repo_name=app_repo_name)
    return resolve_app_tag(provider, env, region, spark_image_url, app_repo_name=app_repo_name)


def registry_has_required_images(provider: str, env: str, region: str) -> bool:
    """
    Check registry has required images (app, spark; kube-proxy for GCP).
    Fetches repo URLs from tofu outputs.
    """
    if provider == "local":
        return True

    if provider == "gcp":
        from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json

        out = get_tofu_output_json(
            "infra_terraform/live_deploy/gcp/scope_shared/nondurable",
            env, region, description="nondurable",
        )
        app_url = (out.get("artifact_registry_app_url", {}) or {}).get("value", "").rstrip("/")
        spark_url = (out.get("artifact_registry_spark_url", {}) or {}).get("value", "").rstrip("/")
        if not app_url or not spark_url:
            return False
        app_image_url = f"{app_url}/app"
        spark_image_url = f"{spark_url}/spark"
        kube_proxy_url = f"{app_url}/kube-proxy"
        return (
            _gcp_artifact_registry_has_image(app_image_url, "latest")
            and _gcp_artifact_registry_has_image(spark_image_url, "latest")
            and _gcp_artifact_registry_has_image(kube_proxy_url, "latest")
        )

    if provider == "aws":
        from tools.aws.scope_shared.deploy.deploy_common import tofu_output_json

        snd = tofu_output_json(
            "infra_terraform/live_deploy/aws/scope_shared/nondurable",
            env, region,
        )
        app_repo_url = (snd.get("ecr_app_url", {}) or {}).get("value", "")
        spark_repo_url = (snd.get("ecr_spark_url", {}) or {}).get("value", "")
        if not app_repo_url or not spark_repo_url:
            return False
        app_repo_name = app_repo_url.split("/")[-1]
        spark_repo_name = spark_repo_url.split("/")[-1]
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

    return False


def get_deploy_image_uris(provider: str, env: str, region: str) -> tuple[str, str]:
    """
    Build full image URIs (app_image_full, spark_image_full).
    Uses APP_IMAGE_TAG from env or resolve_app_tag. Fetches repo URLs from tofu.

    Returns:
        (app_image_full, spark_image_full) e.g. ("repo/app:tag", "repo/spark:tag")
    """
    if provider == "local":
        return ("fru-api:local", "fru-spark:local")

    if provider == "gcp":
        from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json

        out = get_tofu_output_json(
            "infra_terraform/live_deploy/gcp/scope_shared/nondurable",
            env, region, description="nondurable",
        )
        app_base = (out.get("artifact_registry_app_url", {}) or {}).get("value", "").rstrip("/")
        spark_base = (out.get("artifact_registry_spark_url", {}) or {}).get("value", "").rstrip("/")
        if not app_base or not spark_base:
            raise ValueError(
                "artifact_registry_app_url and artifact_registry_spark_url required from nondurable. "
                "Run deploy without --skip-build first."
            )
        app_image_url = f"{app_base}/app"
        tag = resolve_app_tag(provider, env, region, app_image_url)
        return (f"{app_base}/app:{tag}", f"{spark_base}/spark:{tag}")

    if provider == "aws":
        from tools.aws.scope_shared.deploy.deploy_common import tofu_output_json

        snd = tofu_output_json(
            "infra_terraform/live_deploy/aws/scope_shared/nondurable",
            env, region,
        )
        app_repo_url = (snd.get("ecr_app_url", {}) or {}).get("value", "")
        spark_repo_url = (snd.get("ecr_spark_url", {}) or {}).get("value", "")
        if not app_repo_url or not spark_repo_url:
            raise ValueError(
                "ecr_app_url and ecr_spark_url required from nondurable. "
                "Run deploy without --skip-build first."
            )
        app_repo_name = app_repo_url.split("/")[-1]
        tag = resolve_app_tag(provider, env, region, app_repo_url, app_repo_name=app_repo_name)
        return (f"{app_repo_url}:{tag}", f"{spark_repo_url}:{tag}")

    raise ValueError(f"Unknown provider: {provider}")
