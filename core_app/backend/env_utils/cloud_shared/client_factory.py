"""
Factory for creating LLM clients based on environment.
Provider-driven: each provider defines get_llm_client(); factory dispatches by CLOUD_PROVIDER
or falls back to aws → gcp → local (cloud-first).

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]

Chat backend: LLM_INFERENCE_PROVIDER (default claude) selects ModelArk vs cloud Claude path.
GCP provider choice (claude vs gemini): handled inside gcp.get_llm_client() via GCP_LLM_PROVIDER.
"""
from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient
from backend.env_utils.cloud_shared.llm_inference_config import get_llm_inference_provider
from typing import Optional, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

# Fallback order when CLOUD_PROVIDER unset (cloud-first)
_FALLBACK_ORDER = ("aws", "gcp", "local")


def create_llm_client() -> LLMClient:
    """
    Create the appropriate LLM client based on environment.

    Logic:
    1. Resolve LLM_INFERENCE_PROVIDER (default claude).
    2. modelark → ModelArkClient.
    3. claude → CLOUD_PROVIDER explicit dispatch or cloud-first fallback.

    GCP: gcp.get_llm_client() chooses Claude vs Gemini via GCP_LLM_PROVIDER (Option B).
    """
    provider = get_llm_inference_provider()
    logger.info("Creating LLM client for LLM_INFERENCE_PROVIDER=%s", provider)

    if provider == "modelark":
        from backend.env_utils.byteplus.modelark_client import ModelArkClient

        return ModelArkClient()

    explicit = os.environ.get("CLOUD_PROVIDER", "").strip().lower()

    if explicit in ("aws", "gcp", "local"):
        client = _get_provider_client(explicit)
        if client is not None:
            logger.info("Creating LLM client for CLOUD_PROVIDER=%s", explicit)
            return client
        raise ValueError(
            f"No LLM client available for LLM_INFERENCE_PROVIDER=claude and "
            f"CLOUD_PROVIDER={explicit}. "
            f"Check env vars: AWS needs CLOUD_REGION + Bedrock config; "
            f"GCP needs GOOGLE_AI_API_KEY or CLAUDE_API_KEY; local needs CLAUDE_API_KEY."
        )

    for p in _FALLBACK_ORDER:
        client = _get_provider_client(p)
        if client is not None:
            logger.info("Creating LLM client (fallback CLOUD_PROVIDER=%s)", p)
            return client

    raise ValueError(
        "No LLM client available for LLM_INFERENCE_PROVIDER=claude. Set one of:\n"
        "  - CLOUD_PROVIDER=aws + CLOUD_REGION + AWS_BEDROCK_INFERENCE_PROFILE_ID or AWS_BEDROCK_MODEL_ID\n"
        "  - CLOUD_PROVIDER=gcp + GOOGLE_AI_API_KEY\n"
        "  - CLOUD_PROVIDER=local + CLAUDE_API_KEY\n"
        "Or set LLM_INFERENCE_PROVIDER=modelark with ARK_API_KEY + ARK_CHAT_MODEL_ID."
    )


def _get_provider_client(provider: str) -> Optional[LLMClient]:
    """Call provider's get_llm_client()."""
    if provider == "aws":
        from backend.env_utils.aws import get_llm_client as aws_get
        return aws_get()
    if provider == "gcp":
        from backend.env_utils.gcp import get_llm_client as gcp_get
        return gcp_get()
    if provider == "local":
        from backend.env_utils.local import get_llm_client as local_get
        return local_get()
    return None


def claude_complete(
    system_prompt: str,
    user_message: str,
    model_id: Optional[str] = None,
    max_tokens: int = 2000
) -> Dict[str, Any]:
    """Convenience: create client and call complete()."""
    client = create_llm_client()
    return client.complete(system_prompt, user_message, model_id, max_tokens)


def get_bedrock_client():
    """
    Get AWS Bedrock client (for backward compatibility).
    Deprecated for agent path: use create_llm_client() instead.
    """
    from backend.env_utils.cloud_shared.model_config import get_bedrock_region
    import boto3

    region = get_bedrock_region()
    profile = os.environ.get("AWS_PROFILE", "")
    if profile:
        session = boto3.Session(profile_name=profile)
    else:
        session = boto3.Session()
    return session.client("bedrock-runtime", region_name=region)
