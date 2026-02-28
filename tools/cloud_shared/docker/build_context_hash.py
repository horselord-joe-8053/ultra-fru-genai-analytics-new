"""
Build-context hash for content-based build skip. Shared by AWS and GCP.

Compute: hashes files that affect the Docker image.
Storage: AWS uses S3, GCP uses GCS.
"""
import hashlib
import json
import os
import subprocess

_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", ".pytest_cache"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".egg-info", ".egg")


def compute_build_context_hash(context_dir: str, dockerfile_rel: str = "") -> str:
    """
    Compute SHA256 hash of build context (files that affect the Docker image).
    """
    context_dir = os.path.abspath(context_dir)
    h = hashlib.sha256()
    h.update(b"dockerfile:" + dockerfile_rel.encode("utf-8"))

    for root, dirs, files in os.walk(context_dir):
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
                pass
    return h.hexdigest()[:24]


def get_stored_build_hash(bucket: str, key: str, provider: str, region: str | None = None) -> str | None:
    """Fetch stored build hash. provider: 's3' or 'gcs'. For S3, region required."""
    try:
        if provider == "s3":
            out = subprocess.check_output(
                ["aws", "s3", "cp", f"s3://{bucket}/{key}", "-", "--region", region or ""],
                text=True,
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
        elif provider == "gcs":
            out = subprocess.check_output(
                ["gsutil", "cat", f"gs://{bucket}/{key}"],
                text=True,
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
        else:
            return None
        data = json.loads(out)
        return data.get("hash")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        return None


def store_build_hash(
    bucket: str, key: str, provider: str, ctx_hash: str, tag: str, region: str | None = None
) -> None:
    """Write build hash after successful build. provider: 's3' or 'gcs'."""
    data = json.dumps({"hash": ctx_hash, "tag": tag})
    if provider == "s3":
        subprocess.run(
            [
                "aws", "s3", "cp", "-", f"s3://{bucket}/{key}",
                "--region", region or "",
                "--content-type", "application/json",
            ],
            input=data,
            text=True,
            check=True,
            timeout=15,
        )
    elif provider == "gcs":
        subprocess.run(
            ["gsutil", "-q", "-h", "Content-Type:application/json", "cp", "-", f"gs://{bucket}/{key}"],
            input=data,
            text=True,
            check=True,
            timeout=15,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
