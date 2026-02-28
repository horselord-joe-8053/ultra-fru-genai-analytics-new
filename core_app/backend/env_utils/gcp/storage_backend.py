"""
GCS storage backend implementing StorageBackend interface (reference: core_app/backend/env_utils/aws/storage_backend.py).
Wraps gcs_helpers for use by utils/filesystem.py via storage factory.

Applicable environment: [gcp {cloud-run | gke}]
"""
from typing import List

from backend.env_utils.cloud_shared.interfaces.storage_backend import StorageBackend
from backend.env_utils.gcp import gcs_helpers


class GCSStorageBackend(StorageBackend):
    """GCS implementation of StorageBackend."""

    def exists(self, path: str) -> bool:
        """Check if GCS path exists."""
        return gcs_helpers.gcs_exists(path)

    def listdir(self, path: str) -> List[str]:
        """List GCS directory contents."""
        return gcs_helpers.gcs_listdir(path)

    def isdir(self, path: str) -> bool:
        """Check if GCS path is a directory."""
        return gcs_helpers.gcs_isdir(path)
