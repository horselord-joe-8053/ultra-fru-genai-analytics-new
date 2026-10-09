"""
ModelArk chat client (OpenAI-compatible /responses or /chat/completions).

Applicable environment: [local] [aws] [gcp] with HTTPS egress to BytePlus.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, Optional

from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ModelArkClient(LLMClient):
    """HTTP client for ModelArk chat completions."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("ARK_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("ARK_API_KEY must be set for ModelArk client")
        self.base_url = os.environ.get(
            "ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3"
        ).rstrip("/")
        self.model = os.environ.get("ARK_CHAT_MODEL_ID", "").strip()
        if not self.model:
            raise ValueError("ARK_CHAT_MODEL_ID must be set for ModelArk chat")

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
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
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ModelArk HTTP {e.code}: {body}") from e

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        model = model_id or self.model
        data = self._post(
            "/chat/completions",
            {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
        )
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        usage = data.get("usage") or {}
        return {
            "text": text,
            "tokens": {
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
        }

    def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> Iterator[Dict[str, Any]]:
        # Streaming not required for v1; fall back to single completion.
        result = self.complete(system_prompt, user_message, model_id, max_tokens)
        yield {"text": result["text"], "tokens": result["tokens"]}
