"""
GCP GCS-specific file operations (reference: core_app/backend/env_utils/aws/s3_helpers.py).
Provides GCS-compatible file system operations.
Works in GKE/Cloud Run (Workload Identity or service account).

Applicable environment: [gcp {cloud-run | gke}]
"""
from urllib.parse import urlparse
from typing import List
import logging

logger = logging.getLogger(__name__)


def _get_client():
    """Get GCS client. Uses GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_APPLICATION_CREDENTIALS_JSON, or ADC."""
    import os
    import json
    from google.cloud import storage

    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    if creds_json:
        try:
            info = json.loads(creds_json)
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(info)
            return storage.Client(credentials=creds)
        except (json.JSONDecodeError, ValueError):
            pass
    return storage.Client()


def _parse_gs_path(gs_path: str) -> tuple:
    """Parse gs://bucket/key into (bucket, blob_name)."""
    parsed = urlparse(gs_path)
    if parsed.scheme != "gs":
        raise ValueError(f"Invalid GCS path: {gs_path} (expected gs://)")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def gcs_exists(gs_path: str) -> bool:
    """
    Check if GCS path exists.

    Args:
        gs_path: GCS path in format gs://bucket/key

    Returns:
        bool: True if path exists, False otherwise
    """
    bucket_name, blob_name = _parse_gs_path(gs_path)
    client = _get_client()
    bucket = client.bucket(bucket_name)

    if not blob_name or blob_name.endswith("/"):
        # Directory: list with prefix
        blobs = list(bucket.list_blobs(prefix=blob_name or "", max_results=1))
        return len(blobs) > 0

    blob = bucket.blob(blob_name)
    return blob.exists()


def gcs_listdir(gs_path: str) -> List[str]:
    """
    List GCS directory contents.

    Args:
        gs_path: GCS directory path in format gs://bucket/prefix/

    Returns:
        List[str]: List of object names (files and subdirs)
    """
    bucket_name, prefix = _parse_gs_path(gs_path)
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    client = _get_client()
    bucket = client.bucket(bucket_name)
    iterator = bucket.list_blobs(prefix=prefix, delimiter="/")

    items = []
    for blob in iterator:
        rel = blob.name[len(prefix):] if prefix else blob.name
        if rel and "/" not in rel:
            items.append(rel)
    for p in getattr(iterator, "prefixes", []) or []:
        name = p.rstrip("/").split("/")[-1]
        if name:
            items.append(name)
    return items


def gcs_isdir(gs_path: str) -> bool:
    """
    Check if GCS path is a directory.

    Args:
        gs_path: GCS path in format gs://bucket/key

    Returns:
        bool: True if path is a directory, False otherwise
    """
    bucket_name, blob_name = _parse_gs_path(gs_path)
    if not blob_name or blob_name.endswith("/"):
        return True
    return gcs_exists(gs_path.rstrip("/") + "/")
