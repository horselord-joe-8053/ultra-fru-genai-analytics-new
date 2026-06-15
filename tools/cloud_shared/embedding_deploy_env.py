"""
Embedding profile + ModelArk env for API containers (compose, kube api-deployment).

Reads from os.environ / .env at deploy time; not runtime profile resolution.
"""
from __future__ import annotations

import os

DEFAULT_ARK_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
DEFAULT_EMBEDDING_PROFILE = "openai_1536"
DEFAULT_CHAT_CHOICE = "claude_haiku"


def embedding_profile_from_env(default: str = DEFAULT_EMBEDDING_PROFILE) -> str:
    return os.environ.get("EMBEDDING_ACTIVE_PROFILE", default).strip() or default


def expand_model_defaults_for_deploy(
    default_profile: str = DEFAULT_EMBEDDING_PROFILE,
) -> dict[str, str]:
    """
    DEFAULT_* + override policy for compose, kube j2, and Terraform (DRY).

    Aligns container env with runtime model_profiles.py: DEFAULT_EMBEDDING_PROFILE
    wins over legacy EMBEDDING_ACTIVE_PROFILE when set at deploy time.
    """
    embed = (
        os.environ.get("DEFAULT_EMBEDDING_PROFILE", "").strip()
        or os.environ.get("EMBEDDING_ACTIVE_PROFILE", "").strip()
        or default_profile
    )
    chat = os.environ.get("DEFAULT_CHAT_CHOICE", DEFAULT_CHAT_CHOICE).strip() or DEFAULT_CHAT_CHOICE
    allow = os.environ.get("ALLOW_PER_REQUEST_MODEL_OVERRIDE", "true").strip().lower()
    if allow not in ("true", "false", "1", "0", "yes", "no"):
        allow = "true"
    return {
        "EMBEDDING_ACTIVE_PROFILE": embed,
        "DEFAULT_EMBEDDING_PROFILE": embed,
        "DEFAULT_CHAT_CHOICE": chat,
        "ALLOW_PER_REQUEST_MODEL_OVERRIDE": allow,
    }


def modelark_secret_entries() -> dict[str, str]:
    """ARK_API_KEY for k8s app-credentials secret (omit when unset)."""
    key = os.environ.get("ARK_API_KEY", "").strip()
    return {"ARK_API_KEY": key} if key else {}


def llm_inference_provider_from_env(default: str = "claude") -> str:
    raw = os.environ.get("LLM_INFERENCE_PROVIDER", default).strip().lower()
    return raw or default


def api_deployment_embedding_subs(
    default_profile: str = DEFAULT_EMBEDDING_PROFILE,
) -> dict[str, str]:
    """Jinja subs for api-deployment.yaml.j2 embedding + ModelArk + chat provider env block."""
    subs = expand_model_defaults_for_deploy(default_profile)
    subs.update(
        {
            "LLM_INFERENCE_PROVIDER": llm_inference_provider_from_env(),
            "ARK_BASE_URL": os.environ.get("ARK_BASE_URL", DEFAULT_ARK_BASE_URL).strip()
            or DEFAULT_ARK_BASE_URL,
            "ARK_EMBEDDING_MODEL_ID": os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip(),
            "ARK_CHAT_MODEL_ID": os.environ.get("ARK_CHAT_MODEL_ID", "").strip(),
        }
    )
    return subs
