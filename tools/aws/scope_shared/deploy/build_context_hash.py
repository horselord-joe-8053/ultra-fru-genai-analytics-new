"""
Build-context hash for content-based build skip (AWS). Re-exports from cloud_shared.

Usage:
  hash_val = compute_build_context_hash("core_app", "Dockerfile")
  if get_stored_build_hash(bucket, key, region) == hash_val:
      # Skip build
  else:
      # Build, then store_build_hash(bucket, key, region, hash_val, tag)
"""
from tools.cloud_shared.docker.build_context_hash import (
    compute_build_context_hash as _compute,
    get_stored_build_hash as _get_stored,
    store_build_hash as _store,
)


def compute_build_context_hash(context_dir: str, dockerfile_rel: str = "") -> str:
    return _compute(context_dir, dockerfile_rel)


def get_stored_build_hash(bucket: str, key: str, region: str) -> str | None:
    return _get_stored(bucket, key, "s3", region)


def store_build_hash(bucket: str, key: str, region: str, ctx_hash: str, tag: str) -> None:
    _store(bucket, key, "s3", ctx_hash, tag, region)
