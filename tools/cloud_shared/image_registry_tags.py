"""
Centralized image registry tag lookup. Used by deploy (resolve_app_tag) and backend (/version).

Returns tags for the specific image (by digest) from the registry (GCP Artifact Registry,
AWS ECR, or local Docker). Single source of truth for "what tags does this image have".

GCP strategy (two-path for robustness):
  - Primary: OCI Distribution API + Artifact Registry v1 API (works in Cloud Run/GKE with ADC).
  - Fallback: gcloud CLI (works when ADC unavailable, e.g. local dev with gcloud auth).
  Both paths ensure 'latest' is included when it points to the same digest as the build tag.
"""
import json
import logging
import subprocess

__all__ = ["get_image_tags"]

_log = logging.getLogger(__name__)


def _parse_container_image(container_image: str) -> tuple[str, str] | None:
    """Parse 'repo/path:tag' into (repo_base, tag). Returns None if unparseable."""
    if not container_image or ":" not in container_image:
        return None
    repo_base, tag = container_image.rsplit(":", 1)
    if not repo_base or not tag:
        return None
    return (repo_base.strip(), tag.strip())


def _parse_gcp_repo_base(repo_base: str) -> tuple[str, str, str] | None:
    """
    Parse GCP Artifact Registry repo_base into (project, location, repository).
    repo_base: us-central1-docker.pkg.dev/proj/repo/app -> (proj, us-central1, repo)
    package (app) is the image name; v1 API parent is projects/proj/locations/.../repositories/repo.
    """
    if not repo_base or "-docker.pkg.dev" not in repo_base:
        return None
    parts = repo_base.split("/", 1)
    if len(parts) != 2:
        return None
    host, name = parts[0], parts[1]
    location = host.replace("-docker.pkg.dev", "")
    name_parts = name.split("/")
    if len(name_parts) < 2:
        return None
    project = name_parts[0]
    repository = name_parts[1]
    return (project, location, repository)


def _gcp_resolve_digest(repo_base: str, tag: str) -> str | None:
    """
    Resolve image digest via OCI Distribution API or gcloud fallback.
    GET /v2/{name}/manifests/{tag} -> Docker-Content-Digest header.
    """
    # --- Primary: OCI Distribution API (works in Cloud Run/GKE with ADC) ---
    try:
        import urllib.request

        import google.auth
        import google.auth.transport.requests

        parts = repo_base.split("/", 1)
        if len(parts) != 2:
            return None
        host, name = parts[0], parts[1]
        url = f"https://{host}/v2/{name}/manifests/{tag}"
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {credentials.token}")
        # Accept both OCI and Docker v2 manifest formats (Artifact Registry supports both)
        req.add_header(
            "Accept",
            "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            digest = resp.headers.get("Docker-Content-Digest")
            if digest:
                return digest.strip()
    except Exception as e:
        _log.debug("[image_tags] GCP OCI digest lookup failed: %s", e)

    # --- Fallback: gcloud CLI (works when API/auth differs, e.g. local dev with gcloud auth) ---
    try:
        full_ref = f"{repo_base}:{tag}"
        out = subprocess.check_output(
            ["gcloud", "artifacts", "docker", "images", "describe", full_ref,
             "--format", "value(image_summary.digest)"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        digest = (out or "").strip()
        if digest and digest.startswith("sha256:"):
            _log.info("[image_tags] GCP: digest from gcloud fallback: %s...", digest[:20])
            return digest
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        _log.debug("[image_tags] GCP gcloud digest fallback failed: %s", e)
    return None


def _gcp_sort_tags(tags_set: set[str], digest: str, repo_base: str) -> list[str]:
    """Sort tags, put 'latest' first; ensure latest added if digest match."""
    if "latest" not in tags_set:
        latest_digest = _gcp_resolve_digest(repo_base, "latest")
        if latest_digest and latest_digest == digest:
            tags_set.add("latest")
            _log.info("[image_tags] GCP: added 'latest' via fallback (digest match)")
    sorted_tags = sorted(tags_set)
    if "latest" in sorted_tags and sorted_tags[0] != "latest":
        sorted_tags = ["latest"] + [t for t in sorted_tags if t != "latest"]
    _log.info("[image_tags] GCP: returning tags=%s for digest=%s", sorted_tags, digest[:20] + "...")
    return sorted_tags


def _gcp_get_tags_via_gcloud(repo_base: str, digest: str) -> list[str] | None:
    """
    Fallback when Artifact Registry v1 API fails (e.g. no ADC in local env).
    Runs `gcloud artifacts docker tags list` and parses output to find tags for the digest.
    """
    try:
        out = subprocess.check_output(
            ["gcloud", "artifacts", "docker", "tags", "list", repo_base],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        tags_set: set[str] = set()
        for line in (out or "").strip().splitlines():
            if not line or line.startswith("Listing") or line.startswith("TAG "):
                continue
            # Output format: TAG  IMAGE  DIGEST (space-separated columns)
            parts = line.split()
            if len(parts) >= 3 and parts[-1] == digest:
                tags_set.add(parts[0].strip())
        if tags_set:
            _log.info("[image_tags] GCP: tags from gcloud fallback: %s", sorted(tags_set))
            return _gcp_sort_tags(tags_set, digest, repo_base)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        _log.debug("[image_tags] GCP gcloud tags fallback failed: %s", e)
    return None


def _gcp_get_tags(repo_base: str, tag: str) -> list[str] | None:
    """
    Get tags for the specific image (by digest) from GCP Artifact Registry.
    Uses digest resolution + v1 API. Ensures 'latest' is included when it points to same digest.
    """
    digest = _gcp_resolve_digest(repo_base, tag)
    if not digest:
        _log.warning("[image_tags] GCP: failed to resolve digest for %s:%s", repo_base, tag)
        return None

    parsed = _parse_gcp_repo_base(repo_base)
    if not parsed:
        _log.warning("[image_tags] GCP: failed to parse repo_base for %s", repo_base)
        return None
    project, location, repository = parsed

    try:
        import urllib.request

        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        parent = f"projects/{project}/locations/{location}/repositories/{repository}"
        page_token = None
        tags_set: set[str] = set()
        while True:
            url = f"https://artifactregistry.googleapis.com/v1/{parent}/dockerImages?pageSize=100"
            if page_token:
                url += f"&pageToken={page_token}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {credentials.token}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            # Match digest: API may use "sha256:hex" or just "hex" in name/uri
            digest_hex = digest.split(":", 1)[-1] if digest and ":" in digest else digest or ""
            images = data.get("dockerImages") or []
            for img in images:
                name = img.get("name") or ""
                uri = img.get("uri") or ""
                if digest in name or digest in uri or digest_hex in name or digest_hex in uri:
                    tags_set.update(img.get("tags") or [])
            if not tags_set and images:
                _log.warning(
                    "[image_tags] GCP: no match for digest=%s; sample name=%r uri=%r tags=%r",
                    digest[:24] + "..." if digest else None,
                    images[0].get("name"),
                    images[0].get("uri"),
                    images[0].get("tags"),
                )
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        if tags_set:
            return _gcp_sort_tags(tags_set, digest, repo_base)
        _log.warning("[image_tags] GCP: no tags matched digest=%s for %s:%s", digest[:20] + "...", repo_base, tag)
        return None
    except Exception as e:
        _log.warning("[image_tags] GCP: failed to list tags for %s:%s: %s", repo_base, tag, e)
        # Fallback: gcloud artifacts docker tags list (parse output for digest match)
        return _gcp_get_tags_via_gcloud(repo_base, digest)


def _aws_get_tags(repo_base: str, tag: str, region: str) -> list[str] | None:
    """
    Query AWS ECR for all tags on the image with given tag.
    Uses boto3 (available in container) or aws CLI.
    """
    # repo_base: 123456789.dkr.ecr.us-east-1.amazonaws.com/repo_name
    if ".ecr." not in repo_base or ".amazonaws.com" not in repo_base:
        return None
    repo_name = repo_base.split("/")[-1] if "/" in repo_base else repo_base
    try:
        import boto3

        client = boto3.client("ecr", region_name=region)
        resp = client.describe_images(
            repositoryName=repo_name,
            imageIds=[{"imageTag": tag}],
        )
        details = (resp.get("imageDetails") or [])
        if not details:
            return None
        tags = details[0].get("imageTags") or []
        return sorted(tags) if tags else None
    except Exception:
        try:
            out = subprocess.check_output(
                [
                    "aws", "ecr", "describe-images",
                    "--repository-name", repo_name,
                    "--image-ids", f"imageTag={tag}",
                    "--region", region,
                    "--query", "imageDetails[0].imageTags",
                    "--output", "text",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            tags_str = (out or "").strip().replace("\t", ",").replace(" ", ",")
            tags = [t for t in tags_str.split(",") if t]
            return sorted(tags) if tags else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None


def _local_get_tags(container_image: str) -> list[str] | None:
    """Get tags for local Docker image."""
    try:
        out = subprocess.check_output(
            ["docker", "image", "inspect", container_image, "--format", "{{json .RepoTags}}"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        tags = json.loads(out or "[]")
        return sorted(tags) if isinstance(tags, list) and tags else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def get_image_tags(
    container_image: str,
    provider: str,
    region: str | None = None,
) -> list[str]:
    """
    Return tags for the specific image (by digest) from the registry.

    Args:
        container_image: Full image reference (e.g. repo/app:fru_dev_xxx)
        provider: "gcp" | "aws" | "local"
        region: Cloud region (us-central1, us-east-1). Required for gcp/aws.

    Returns:
        Sorted list of tags for that image. Falls back to [tag] from container_image if lookup fails.
    """
    parsed = _parse_container_image(container_image)
    if not parsed:
        _log.warning("[image_tags] unparseable container_image=%r", container_image[:80] if container_image else "")
        return []
    repo_base, tag = parsed

    if provider == "local":
        tags = _local_get_tags(container_image)
    elif provider == "gcp" and region:
        tags = _gcp_get_tags(repo_base, tag)
    elif provider == "aws" and region:
        tags = _aws_get_tags(repo_base, tag, region)
    else:
        tags = None

    if tags:
        _log.info("[image_tags] provider=%s region=%s: tags=%s", provider, region, tags)
        return tags
    _log.warning("[image_tags] registry lookup failed, falling back to [%s]", tag)
    return [tag]  # Fallback to known tag when registry lookup fails
