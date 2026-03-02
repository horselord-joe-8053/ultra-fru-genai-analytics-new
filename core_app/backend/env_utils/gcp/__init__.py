"""
GCP cloud environment utilities (reference: core_app/backend/env_utils/aws/__init__.py).
Contains implementations for GCP services:
- gemini_api_client: LLM via Gemini API (Google AI Studio)
- local claude_client: LLM via Anthropic Claude API (when GCP_LLM_PROVIDER=claude)

Applicable environment: [gcp {cloud-run | gke}]

Rationale for provider choice (Option B): GCP containers (Cloud Run nonkube, GKE kube) can use
either Gemini or Claude. Gemini free tier has low RPD (20/day); paid tier has RPD limits too.
Claude API avoids Gemini quota. Provider selection lives in GCP module so the factory stays
generic; each provider owns its own client selection logic.
"""
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient


def get_llm_client() -> Optional["LLMClient"]:
    """
    Return LLM client for GCP: Claude or Gemini based on GCP_LLM_PROVIDER.

    When GCP_LLM_PROVIDER=claude (or LLM_PROVIDER=claude) and CLAUDE_API_KEY is set,
    returns LocalClaudeClient (Anthropic API). Otherwise returns GCPGeminiAPIClient when
    GOOGLE_AI_API_KEY (or fallbacks) is set.

    Works for both nonkube (Cloud Run) and kube (GKE): same backend code runs in either
    container; env vars must be passed at deploy time. Nonkube: Terraform wires
    GCP_LLM_PROVIDER, CLAUDE_API_KEY, GOOGLE_AI_API_KEY. Kube: if API is deployed via
    Helm/K8s, pass the same env vars to the API deployment.
    """
    # GCP_LLM_PROVIDER preferred; LLM_PROVIDER fallback for Terraform/deploy compatibility
    llm_provider = (
        os.environ.get("GCP_LLM_PROVIDER", "").strip().lower()
        or os.environ.get("LLM_PROVIDER", "").strip().lower()
    )

    if llm_provider == "claude":
        claude_key = os.environ.get("CLAUDE_API_KEY", "").strip()
        if claude_key:
            try:
                from backend.env_utils.local.claude_client import LocalClaudeClient
                return LocalClaudeClient()
            except Exception:
                return None
        # CLAUDE_API_KEY missing; fall through to Gemini if available

    # Default: Gemini (Google AI Studio)
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
