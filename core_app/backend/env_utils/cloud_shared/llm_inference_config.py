"""
Explicit chat inference provider contract (orthogonal to EMBEDDING_ACTIVE_PROFILE).

Extend new chat backends by: (1) add to ALLOWED_LLM_INFERENCE_PROVIDERS,
(2) add a factory branch in client_factory.py, (3) add an envex comment row in .env.example.
"""
from __future__ import annotations

import os

DEFAULT_LLM_INFERENCE_PROVIDER = "claude"
ALLOWED_LLM_INFERENCE_PROVIDERS: frozenset[str] = frozenset({"claude", "modelark"})


def get_llm_inference_provider() -> str:
    """Return normalized LLM_INFERENCE_PROVIDER; default claude when unset or empty."""
    raw = (os.environ.get("LLM_INFERENCE_PROVIDER") or "").strip().lower()
    if not raw:
        return DEFAULT_LLM_INFERENCE_PROVIDER
    if raw not in ALLOWED_LLM_INFERENCE_PROVIDERS:
        allowed = ", ".join(sorted(ALLOWED_LLM_INFERENCE_PROVIDERS))
        raise ValueError(
            f"LLM_INFERENCE_PROVIDER={raw!r} is not allowed. "
            f"Allowed values: {allowed}. Default: {DEFAULT_LLM_INFERENCE_PROVIDER}."
        )
    return raw


def chat_model_env_for_provider(
    provider: str | None = None,
    *,
    cloud_provider: str | None = None,
) -> dict[str, str]:
    """Primary model/credential env vars for the chat provider (doctor/docs)."""
    p = (provider or get_llm_inference_provider()).strip().lower()
    cp = (cloud_provider or os.environ.get("CLOUD_PROVIDER") or "local").strip().lower()

    if p == "modelark":
        return {
            "ARK_API_KEY": "ModelArk API key",
            "ARK_BASE_URL": "ModelArk API base URL",
            "ARK_CHAT_MODEL_ID": "ModelArk chat model id",
        }

    if cp == "aws":
        return {
            "AWS_BEDROCK_INFERENCE_PROFILE_ID": "Bedrock inference profile (or AWS_BEDROCK_MODEL_ID)",
            "AWS_BEDROCK_MODEL_ID": "Bedrock model id (alternative to profile)",
        }
    if cp == "gcp":
        gcp_llm = (
            os.environ.get("GCP_LLM_PROVIDER", "").strip().lower()
            or os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
        )
        if gcp_llm == "claude":
            return {
                "CLAUDE_API_KEY": "Anthropic API key",
                "CLAUDE_MODEL": "Claude model id",
            }
        return {
            "GOOGLE_AI_API_KEY": "Google AI API key",
            "GOOGLE_MODEL": "Gemini model id",
        }
    return {
        "CLAUDE_API_KEY": "Anthropic API key",
        "CLAUDE_MODEL": "Claude model id",
    }
