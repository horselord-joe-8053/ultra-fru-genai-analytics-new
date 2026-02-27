"""
Abstract interfaces for cloud-agnostic implementations.
All concrete implementations (AWS, GCP, local) implement these interfaces.
"""

from .llm_client import LLMClient
from .storage_backend import StorageBackend

__all__ = ["LLMClient", "StorageBackend"]
