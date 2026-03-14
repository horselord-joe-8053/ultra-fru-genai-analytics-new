"""
Single source of truth for LLM model identifiers from .env.

All model attributes must be set in .env; no defaults. Missing values raise with a clear message.
Use these helpers everywhere so we fail-fast and stay DRY.
"""
import os

_ENV_MSG = "Set it in .env (see .env.example)."


def require_claude_model() -> str:
    """Return CLAUDE_MODEL from .env. Raises if missing."""
    v = (os.environ.get("CLAUDE_MODEL") or "").strip()
    if not v:
        raise ValueError(
            "CLAUDE_MODEL is required and must be set. "
            + _ENV_MSG
        )
    return v


def require_google_model() -> str:
    """Return GOOGLE_MODEL or GEMINI_MODEL from .env. Raises if both missing."""
    v = (
        (os.environ.get("GOOGLE_MODEL") or "").strip()
        or (os.environ.get("GEMINI_MODEL") or "").strip()
    )
    if not v:
        raise ValueError(
            "GOOGLE_MODEL or GEMINI_MODEL is required and must be set. "
            + _ENV_MSG
        )
    return v


def require_bedrock_model_id() -> str:
    """Return AWS_BEDROCK_MODEL_ID from .env. Raises if missing."""
    v = (os.environ.get("AWS_BEDROCK_MODEL_ID") or "").strip()
    if not v:
        raise ValueError(
            "AWS_BEDROCK_MODEL_ID is required and must be set. "
            + _ENV_MSG
        )
    return v


def get_bedrock_inference_profile_id() -> str:
    """Return AWS_BEDROCK_INFERENCE_PROFILE_ID from .env (may be empty)."""
    return (os.environ.get("AWS_BEDROCK_INFERENCE_PROFILE_ID") or "").strip()


def get_bedrock_region() -> str:
    """Return Bedrock API region. Prefer AWS_BEDROCK_REGION (us-east-1 for most models); fallback to CLOUD_REGION."""
    return (
        (os.environ.get("AWS_BEDROCK_REGION") or "").strip()
        or (os.environ.get("CLOUD_REGION") or "").strip()
        or "us-east-1"
    )
