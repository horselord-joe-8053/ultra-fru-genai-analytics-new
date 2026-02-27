"""
LLMClient interface — re-exported from env_utils.cloud_shared for backward compatibility.
New code should import from backend.env_utils.cloud_shared.interfaces.llm_client.
"""
from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient

__all__ = ["LLMClient"]

