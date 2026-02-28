"""
GCP cloud environment utilities (reference: core_app/backend/env_utils/aws/__init__.py).
Contains implementations for GCP services:
- gemini_api_client: LLM via Gemini API (Google AI Studio)

Applicable environment: [gcp {cloud-run | gke}]
"""
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient


def get_llm_client() -> Optional["LLMClient"]:
    """Return GCPGeminiAPIClient if GCP LLM config present, else None."""
    api_key = (
        os.environ.get("GOOGLE_AI_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
    )
    if not api_key:
        return None
    try:
        from backend.env_utils.gcp.gemini_api_client import GCPGeminiAPIClient
        return GCPGeminiAPIClient()
    except Exception:
        return None
