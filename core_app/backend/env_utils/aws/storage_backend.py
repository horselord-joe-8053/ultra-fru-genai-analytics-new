"""
S3 storage backend implementing StorageBackend interface.
Wraps s3_helpers for use by utils/filesystem.py via storage factory.

Applicable environment: [aws {ecs | eks}]
"""
from typing import List

from backend.env_utils.cloud_shared.interfaces.storage_backend import StorageBackend
from backend.env_utils.aws import s3_helpers


class S3StorageBackend(StorageBackend):
    """S3 implementation of StorageBackend."""

    def exists(self, path: str) -> bool:
        """Check if S3 path exists. Accepts s3:// or s3a:// (normalized to s3://)."""
        normalized = path.replace("s3a://", "s3://", 1) if path.startswith("s3a://") else path
        return s3_helpers.s3_exists(normalized)

    def listdir(self, path: str) -> List[str]:
        """List S3 directory contents."""
        return s3_helpers.s3_listdir(path)

    def isdir(self, path: str) -> bool:
        """Check if S3 path is a directory."""
        return s3_helpers.s3_isdir(path)
