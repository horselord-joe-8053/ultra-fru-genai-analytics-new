"""
Storage backend factory.
Returns the appropriate StorageBackend based on path prefix or storage type.
Used by utils/filesystem.py to avoid direct cloud-specific imports.

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""
from typing import Optional

from backend.env_utils.cloud_shared.interfaces.storage_backend import StorageBackend


def detect_storage_type(path: str) -> str:
    """
    Detect storage type from path prefix.

    Returns:
        's3' for s3:// or s3a://
        'gcs' for gs://
        'efs' for /mnt/efs/
        'local' for other paths
    """
    if path.startswith("s3://") or path.startswith("s3a://"):
        return "s3"
    if path.startswith("gs://"):
        return "gcs"
    if path.startswith("/mnt/efs/"):
        return "efs"
    return "local"


def get_storage_backend(path: Optional[str] = None, storage_type: Optional[str] = None) -> StorageBackend:
    """
    Get the appropriate StorageBackend for the given path or storage type.

    Args:
        path: Path to infer storage type from (e.g. s3://bucket/key, /local/path)
        storage_type: Explicit storage type ('s3', 'gcs', 'efs', 'local')

    Returns:
        StorageBackend implementation

    Raises:
        NotImplementedError: For gcs (GCP not yet implemented)
    """
    if storage_type is None and path is not None:
        storage_type = detect_storage_type(path)
    if storage_type is None:
        storage_type = "local"

    if storage_type == "s3":
        from backend.env_utils.aws.storage_backend import S3StorageBackend
        return S3StorageBackend()
    if storage_type in ("local", "efs"):
        # EFS is mounted, so use local filesystem ops
        from backend.env_utils.local.storage_backend import LocalStorageBackend
        return LocalStorageBackend()
    if storage_type == "gcs":
        raise NotImplementedError(
            "GCS storage backend not yet implemented. "
            "See REFACTOR_PLAN_GCP_READINESS.md Phase 1 for gcs_helpers.py."
        )
    # Default to local
    from backend.env_utils.local.storage_backend import LocalStorageBackend
    return LocalStorageBackend()
