"""
Build-context hash for content-based build skip.

Enables deploy to skip Docker build when source code hasn't changed. Hashes the
files that go into the image (Dockerfile + source in context_dir). Captures
both committed and uncommitted changes—so local edits before commit will
correctly trigger a rebuild.

Flow:
  1. Before build: compute current hash, fetch stored hash from S3.
  2. If match: skip build (use repo:latest from ECR).
  3. If no match or no stored hash: build, push, then store hash to S3.

Storage: s3://{artifacts_bucket}/build-metadata/{env}/app-build-hash.json
         and spark-build-hash.json. Each contains {"hash": "...", "tag": "..."}.

Why not git SHA only? Git SHA ignores uncommitted changes. A developer testing
local edits would get a false "skip" and deploy stale code. Hashing file
contents captures any change.

Usage:
  hash_val = compute_build_context_hash("core_app", "Dockerfile")
  if get_stored_build_hash(bucket, key, region) == hash_val:
      # Skip build
  else:
      # Build, then store_build_hash(bucket, key, region, hash_val, tag)
"""
import hashlib
import json
import os
import subprocess

# Paths to exclude from hash. These don't affect the image; hashing them would
# cause unnecessary rebuilds (e.g. node_modules is rebuilt in-container from
# package.json). Align with typical .dockerignore patterns.
_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", ".pytest_cache"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".egg-info", ".egg")


def compute_build_context_hash(context_dir: str, dockerfile_rel: str = "") -> str:
    """
    Compute SHA256 hash of build context (files that affect the Docker image).

    Args:
        context_dir: Root of build context (e.g. "core_app").
        dockerfile_rel: Path to Dockerfile relative to context (e.g. "Dockerfile"
            for app, "analytics/docker/Dockerfile" for spark). Included so app
            and spark get different hashes even when sharing the same context.

    Returns:
        24-char hex digest. Includes all non-excluded files; any change to
        source, Dockerfile, or config changes the hash.
    """
    context_dir = os.path.abspath(context_dir)
    h = hashlib.sha256()
    h.update(b"dockerfile:" + dockerfile_rel.encode("utf-8"))

    for root, dirs, files in os.walk(context_dir):
        # Skip excluded dirs (modifies dirs in-place to prune walk)
        dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS and not d.startswith(".")]
        for f in sorted(files):
            if f.endswith(_EXCLUDE_SUFFIXES):
                continue
            path = os.path.join(root, f)
            try:
                rel = os.path.relpath(path, context_dir)
                with open(path, "rb") as fp:
                    h.update(rel.encode("utf-8") + b":" + fp.read() + b"\n")
            except (OSError, IOError):
                pass  # Skip unreadable files
    return h.hexdigest()[:24]


def get_stored_build_hash(bucket: str, key: str, region: str) -> str | None:
    """
    Fetch stored build hash from S3 (from a previous successful build).

    Returns None if object doesn't exist, JSON is invalid, or AWS call fails.
    Used by deploy to decide whether to skip build.
    """
    try:
        out = subprocess.check_output(
            [
                "aws", "s3", "cp",
                f"s3://{bucket}/{key}",
                "-",
                "--region", region,
            ],
            text=True,
            timeout=15,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(out)
        return data.get("hash")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        return None


def store_build_hash(bucket: str, key: str, region: str, ctx_hash: str, tag: str) -> None:
    """
    Write build hash to S3 after a successful build and push.

    Call this only after images are pushed to ECR. The stored hash enables
    future deploys to skip build when compute_build_context_hash() matches.
    """
    data = json.dumps({"hash": ctx_hash, "tag": tag})
    subprocess.run(
        [
            "aws", "s3", "cp",
            "-",
            f"s3://{bucket}/{key}",
            "--region", region,
            "--content-type", "application/json",
        ],
        input=data,
        text=True,
        check=True,
        timeout=15,
    )
