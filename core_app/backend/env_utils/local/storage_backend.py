"""
Local filesystem storage backend implementing StorageBackend interface.
Used for local paths and mounted storage (e.g. EFS at /mnt/efs/).

Applicable environment: [local] [aws {ecs | eks}] (EFS)
"""
import os
from typing import List

from backend.env_utils.cloud_shared.interfaces.storage_backend import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Local filesystem implementation of StorageBackend."""

    def exists(self, path: str) -> bool:
        """Check if local path exists."""
        return os.path.exists(path)

    def listdir(self, path: str) -> List[str]:
        """List local directory contents."""
        return os.listdir(path)

    def isdir(self, path: str) -> bool:
        """Check if local path is a directory."""
        return os.path.isdir(path)
