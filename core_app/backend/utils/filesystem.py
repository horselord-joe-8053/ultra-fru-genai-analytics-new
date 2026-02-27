"""
File system abstraction for multi-environment support.
Works with local, S3, EFS, and future storage backends (GCS).
Uses StorageBackend factory — no direct cloud-specific imports.

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""
from typing import List
import logging

from backend.env_utils.cloud_shared.storage_factory import (
    detect_storage_type as _detect_storage_type,
    get_storage_backend,
)

logger = logging.getLogger(__name__)


def detect_storage_type(path: str) -> str:
    """
    Detect storage type from path.

    Returns:
        's3' for S3 paths (s3://bucket/key or s3a://bucket/key)
        'gcs' for GCS paths (gs://bucket/key)
        'efs' for EFS paths (/mnt/efs/...)
        'local' for local file system paths
    """
    return _detect_storage_type(path)


def exists(path: str) -> bool:
    """
    Check if path exists (works for S3, local, EFS, and GCS when implemented).

    Args:
        path: File or directory path (can be s3://, s3a://, gs://, /mnt/efs/, or local)

    Returns:
        bool: True if path exists, False otherwise

    Raises:
        NotImplementedError: For gs:// paths until GCP storage is implemented
    """
    storage_type = detect_storage_type(path)
    logger.debug(f"Checking if path exists: {path} (storage_type={storage_type})")
    backend = get_storage_backend(path=path)
    result = backend.exists(path)
    logger.debug(f"Path exists check result: {result} for {path}")
    return result


def listdir(path: str) -> List[str]:
    """
    List directory contents (works for S3, local, EFS, and GCS when implemented).

    Args:
        path: Directory path (can be s3://, gs://, /mnt/efs/, or local)

    Returns:
        List[str]: List of file/directory names

    Raises:
        NotImplementedError: For gs:// paths until GCP storage is implemented
    """
    backend = get_storage_backend(path=path)
    return backend.listdir(path)


def isdir(path: str) -> bool:
    """
    Check if path is a directory (works for S3, local, EFS, and GCS when implemented).

    Args:
        path: Path to check (can be s3://, gs://, /mnt/efs/, or local)

    Returns:
        bool: True if path is a directory, False otherwise

    Raises:
        NotImplementedError: For gs:// paths until GCP storage is implemented
    """
    backend = get_storage_backend(path=path)
    return backend.isdir(path)
