"""
GCP Gemini API client (Google AI Studio) (reference: core_app/backend/env_utils/aws/bedrock_client.py).
Implements LLMClient interface for Gemini API usage.
Uses google-genai SDK with API key (not Vertex AI).

Applicable environment: [gcp {cloud-run | gke}]
"""
from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient
import os
import logging
from typing import Dict, Any, Optional, Iterator

logger = logging.getLogger(__name__)

# Default model when GOOGLE_MODEL/GEMINI_MODEL not set
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GCPGeminiAPIClient(LLMClient):
    """Gemini API client (Google AI Studio, API key auth)."""

    def __init__(self):
        api_key = (
            os.environ.get("GOOGLE_AI_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )
        if not api_key:
            raise ValueError(
                "GOOGLE_AI_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY must be set for Gemini API"
            )
        from google import genai

        self.client = genai.Client(api_key=api_key)
        # Model from .env; GOOGLE_MODEL preferred, GEMINI_MODEL fallback (user preference)
        self.model = (
            os.environ.get("GOOGLE_MODEL", "").strip()
            or os.environ.get("GEMINI_MODEL", "").strip()
            or _DEFAULT_GEMINI_MODEL
        )

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Generate completion using Gemini API."""
        from google.genai import types

        model = model_id or self.model
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        )
        response = self.client.models.generate_content(
            model=model,
            contents=user_message,
            config=config,
        )
        text = response.text or ""
        usage = getattr(response, "usage_metadata", None)
        input_tokens = output_tokens = 0
        if usage:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or getattr(usage, "output_token_count", 0) or 0
        total = input_tokens + output_tokens
        return {
            "text": text,
            "tokens": {
                "input": input_tokens or 0,
                "output": output_tokens or 0,
                "total": total,
            },
        }

    def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        max_tokens: int = 2000
    ) -> Iterator[Dict[str, Any]]:
        """Generate streaming completion using Gemini API."""
        from google.genai import types

        model = model_id or self.model
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        )
        for chunk in self.client.models.generate_content_stream(
            model=model,
            contents=user_message,
            config=config,
        ):
            text = chunk.text if hasattr(chunk, "text") else ""
            if text:
                yield {"text": text, "tokens": {}}
