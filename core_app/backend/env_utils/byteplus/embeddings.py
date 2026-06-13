"""
ModelArk embedding client (OpenAI-compatible /embeddings endpoint).

Applicable environment: [local] [aws] [gcp] with ARK_API_KEY + ARK_EMBEDDING_MODEL_ID.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import List

from backend.env_utils.cloud_shared.embedding_profiles import EmbeddingProfile, resolve_model_id
from backend.env_utils.cloud_shared.interfaces.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


class ModelArkEmbeddingClient(EmbeddingClient):
    def __init__(self, profile: EmbeddingProfile) -> None:
        self._profile = profile
        self.api_key = os.environ.get("ARK_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("ARK_API_KEY must be set for ModelArk embeddings")
        self.base_url = os.environ.get(
            "ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3"
        ).rstrip("/")
        self.model_id = resolve_model_id(profile)

    @property
    def profile_name(self) -> str:
        return self._profile.name

    @property
    def dimension(self) -> int:
        return self._profile.dimension

    def _uses_multimodal_endpoint(self) -> bool:
        """Skylark embedding-vision models use /embeddings/multimodal, not /embeddings."""
        return "embedding-vision" in self.model_id.lower()

    def _post_json(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        text_len = 0
        if path.endswith("/multimodal"):
            inputs = payload.get("input") or []
            if inputs and isinstance(inputs[0], dict):
                text_len = len(inputs[0].get("text") or "")
        else:
            inp = payload.get("input")
            if isinstance(inp, list) and inp:
                text_len = sum(len(str(x)) for x in inp)
            elif isinstance(inp, str):
                text_len = len(inp)
        t0 = time.monotonic()
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "modelark_embed: profile=%s path=%s model=%s text_chars=%d http=%d ms=%d",
                self.profile_name,
                path,
                payload.get("model", self.model_id),
                text_len,
                resp.status,
                elapsed_ms,
            )
            return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.warning(
                "modelark_embed: profile=%s path=%s model=%s http=%d ms=%d body=%s",
                self.profile_name,
                path,
                payload.get("model", self.model_id),
                e.code,
                elapsed_ms,
                body[:500],
            )
            raise RuntimeError(f"ModelArk embeddings HTTP {e.code}: {body}") from e

    def _validate_vector(self, vec: List[float]) -> List[float]:
        if len(vec) != self.dimension:
            raise ValueError(
                f"ModelArk returned dimension {len(vec)}; expected {self.dimension} "
                f"for profile {self.profile_name}"
            )
        return vec

    def _embed_multimodal_text(self, text: str) -> List[float]:
        data = self._post_json(
            "/embeddings/multimodal",
            {
                "model": self.model_id,
                "encoding_format": "float",
                "input": [{"type": "text", "text": text}],
            },
        )
        block = data.get("data") or {}
        vec = block.get("embedding")
        if not isinstance(vec, list):
            raise RuntimeError(
                f"ModelArk multimodal response missing data.embedding: {data!r}"
            )
        logger.info(
            "modelark_embed: profile=%s response_dim=%d expected_dim=%d",
            self.profile_name,
            len(vec),
            self.dimension,
        )
        return self._validate_vector(vec)

    def _embed_openai_compatible_batch(self, texts: List[str]) -> List[List[float]]:
        data = self._post_json(
            "/embeddings",
            {"model": self.model_id, "input": texts},
        )
        items = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
        vectors = [item["embedding"] for item in items]
        return [self._validate_vector(vec) for vec in vectors]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._uses_multimodal_endpoint():
            return [self._embed_multimodal_text(text) for text in texts]
        return self._embed_openai_compatible_batch(texts)
