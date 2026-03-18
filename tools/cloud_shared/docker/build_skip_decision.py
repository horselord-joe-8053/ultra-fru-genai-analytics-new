"""
Unified build-skip decision for content-hash strategy. Shared by Local, AWS, and GCP.

Callers supply storage config (bucket/keys/provider) and optional registry_has_images();
this module returns whether to skip the build and the hashes needed for logging or storing after build.
"""
from dataclasses import dataclass
from typing import Callable

from tools.cloud_shared.docker.build_context_hash import (
    compute_build_context_hash,
    get_stored_build_hash,
)


@dataclass
class BuildSkipResult:
    """Result of the content-hash build-skip check."""

    skip: bool
    """True if build should be skipped (hash match and registry satisfied)."""
    app_hash: str
    spark_hash: str | None
    stored_app: str | None
    stored_spark: str | None
    skip_reason: str | None
    """Message to log when skip is True (e.g. 'content hash matches stored (GCS). Use --force-build to rebuild.')."""


def decide_build_skip(
    *,
    force_build: bool,
    storage_bucket: str,
    app_key: str,
    spark_key: str,
    provider: str,
    region: str | None = None,
    skip_spark: bool = False,
    registry_has_images: Callable[[], bool] | None = None,
    storage_label: str | None = None,
    skip_reason_override: str | None = None,
) -> BuildSkipResult:
    """
    Decide whether to skip the image build using the content-hash strategy.

    Args:
        force_build: If True, never skip (return skip=False).
        storage_bucket: S3 bucket, GCS bucket name, or local memo dir (for provider "local").
        app_key: Key/path for stored app hash (e.g. "build-metadata/dev/app-build-hash.json").
        spark_key: Key/path for stored spark hash.
        provider: "s3" | "gcs" | "local".
        region: Required for S3; unused for gcs/local.
        skip_spark: If True, only app hash is compared; spark is considered matched.
        registry_has_images: Optional callback. If provided and hashes match, we skip only when
            this returns True (e.g. GCP checks Artifact Registry). If None (Local/AWS-style),
            we skip whenever hashes match.
        storage_label: Short label for skip message (e.g. "memo/", "GCS", "S3"). Defaults from provider.
        skip_reason_override: When skip is True, use this message instead of the default (e.g. GCP adds "and registry already has ...").

    Returns:
        BuildSkipResult with skip, hashes, and skip_reason (when skip is True).
    """
    label = storage_label or {"s3": "S3", "gcs": "GCS", "local": "memo/"}.get(provider, provider)
    app_hash = compute_build_context_hash("core_app", "Dockerfile")
    tools_hash = compute_build_context_hash("tools/cloud_shared", "")
    app_hash = f"{app_hash}_{tools_hash[:12]}" if tools_hash else app_hash
    spark_hash = None if skip_spark else compute_build_context_hash("core_app", "analytics/docker/Dockerfile")
    stored_app = get_stored_build_hash(storage_bucket, app_key, provider, region)
    stored_spark = None if skip_spark else get_stored_build_hash(storage_bucket, spark_key, provider, region)

    if force_build:
        return BuildSkipResult(
            skip=False,
            app_hash=app_hash,
            spark_hash=spark_hash,
            stored_app=stored_app,
            stored_spark=stored_spark,
            skip_reason=None,
        )

    hashes_match = stored_app == app_hash and (skip_spark or stored_spark == spark_hash)
    if not hashes_match:
        return BuildSkipResult(
            skip=False,
            app_hash=app_hash,
            spark_hash=spark_hash,
            stored_app=stored_app,
            stored_spark=stored_spark,
            skip_reason=None,
        )

    if registry_has_images is not None and not registry_has_images():
        return BuildSkipResult(
            skip=False,
            app_hash=app_hash,
            spark_hash=spark_hash,
            stored_app=stored_app,
            stored_spark=stored_spark,
            skip_reason=None,
        )

    skip_reason = skip_reason_override or f"content hash matches stored ({label}). Use --force-build to rebuild."
    return BuildSkipResult(
        skip=True,
        app_hash=app_hash,
        spark_hash=spark_hash,
        stored_app=stored_app,
        stored_spark=stored_spark,
        skip_reason=skip_reason,
    )
