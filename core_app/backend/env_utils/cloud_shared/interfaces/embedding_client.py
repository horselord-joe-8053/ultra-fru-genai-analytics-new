"""
Abstract embedding client — OpenAI, ModelArk, and future providers.

Applicable environment: [local] [aws] [gcp]
"""
from abc import ABC, abstractmethod
from typing import List


class EmbeddingClient(ABC):
    """Generate dense vectors for semantic search and CRUD upsert."""

    @property
    @abstractmethod
    def profile_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector per input text (same order)."""
        pass
