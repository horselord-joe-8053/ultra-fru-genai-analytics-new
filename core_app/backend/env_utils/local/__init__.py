"""
Local development environment utilities.

Applicable environment: [local]
"""
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient


def get_llm_client() -> Optional["LLMClient"]:
    """Return LocalClaudeClient if CLAUDE_API_KEY is set, else None."""
    if not os.environ.get("CLAUDE_API_KEY", "").strip():
        return None
    try:
        from backend.env_utils.local.claude_client import LocalClaudeClient
        return LocalClaudeClient()
    except Exception:
        return None

