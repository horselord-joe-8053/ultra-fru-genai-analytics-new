"""
Factory for embedding clients driven by embedding_profiles.yaml.

Write paths (embedding_sync, CRUD) must pass explicit profile= to create_embedding_client().
Default (active profile) is for query-time search and user-question embedding only.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from openai import OpenAI

from backend.env_utils.cloud_shared.embedding_profiles import (
    EmbeddingProfile,
    get_active_profile,
    resolve_model_id,
)
from backend.env_utils.cloud_shared.interfaces.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, profile: EmbeddingProfile, openai_client: Optional[OpenAI] = None) -> None:
        self._profile = profile
        if openai_client is not None:
            self._client = openai_client
        else:
            from backend.utils.env_helpers import get_required_env

            api_key = get_required_env("OPENAI_API_KEY", "OpenAI API key for embeddings")
            self._client = OpenAI(api_key=api_key)
        self._model = resolve_model_id(profile)

    @property
    def profile_name(self) -> str:
        return self._profile.name

    @property
    def dimension(self) -> int:
        return self._profile.dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        total_chars = sum(len(t) for t in texts)
        t0 = time.monotonic()
        response = self._client.embeddings.create(model=self._model, input=texts)
        ordered = sorted(response.data, key=lambda d: d.index)
        vectors = [d.embedding for d in ordered]
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "openai_embed: profile=%s model=%s batch=%d chars=%d dim=%d ms=%d",
            self.profile_name,
            self._model,
            len(texts),
            total_chars,
            len(vectors[0]) if vectors else 0,
            elapsed_ms,
        )
        return vectors


def create_embedding_client(
    profile: EmbeddingProfile | None = None,
    openai_client: Optional[OpenAI] = None,
) -> EmbeddingClient:
    """Return embedding client for active or explicit profile."""
    prof = profile or get_active_profile()
    logger.debug("Creating embedding client for profile=%s provider=%s", prof.name, prof.provider)
    if prof.provider == "openai":
        return OpenAIEmbeddingClient(prof, openai_client=openai_client)
    if prof.provider == "modelark":
        from backend.env_utils.byteplus.embeddings import ModelArkEmbeddingClient

        return ModelArkEmbeddingClient(prof)
    raise ValueError(f"Unsupported embedding provider: {prof.provider}")
