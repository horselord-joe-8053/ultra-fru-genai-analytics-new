"""
Abstract base class for storage backends.
All storage implementations (S3, GCS, local filesystem) must implement this interface.
Enables provider-agnostic file operations in utils/filesystem.py.

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""
from abc import ABC, abstractmethod
from typing import List


class StorageBackend(ABC):
    """Abstract base class for storage backends (S3, GCS, local)."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if path exists.

        Args:
            path: File or directory path (e.g. s3://bucket/key, gs://bucket/key, /local/path)

        Returns:
            True if path exists, False otherwise
        """
        pass

    @abstractmethod
    def listdir(self, path: str) -> List[str]:
        """
        List directory contents.

        Args:
            path: Directory path

        Returns:
            List of file/directory names
        """
        pass

    @abstractmethod
    def isdir(self, path: str) -> bool:
        """
        Check if path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory, False otherwise
        """
        pass
