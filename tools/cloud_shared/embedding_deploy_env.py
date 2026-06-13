"""
Embedding profile + ModelArk env for API containers (compose, kube api-deployment).

Reads from os.environ / .env at deploy time; not runtime profile resolution.
"""
from __future__ import annotations

import os

DEFAULT_ARK_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
DEFAULT_EMBEDDING_PROFILE = "openai_1536"


def embedding_profile_from_env(default: str = DEFAULT_EMBEDDING_PROFILE) -> str:
    return os.environ.get("EMBEDDING_ACTIVE_PROFILE", default).strip() or default


def modelark_secret_entries() -> dict[str, str]:
    """ARK_API_KEY for k8s app-credentials secret (omit when unset)."""
    key = os.environ.get("ARK_API_KEY", "").strip()
    return {"ARK_API_KEY": key} if key else {}


def api_deployment_embedding_subs(
    default_profile: str = DEFAULT_EMBEDDING_PROFILE,
) -> dict[str, str]:
    """Jinja subs for api-deployment.yaml.j2 embedding + ModelArk env block."""
    return {
        "EMBEDDING_ACTIVE_PROFILE": embedding_profile_from_env(default_profile),
        "ARK_BASE_URL": os.environ.get("ARK_BASE_URL", DEFAULT_ARK_BASE_URL).strip()
        or DEFAULT_ARK_BASE_URL,
        "ARK_EMBEDDING_MODEL_ID": os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip(),
        "ARK_CHAT_MODEL_ID": os.environ.get("ARK_CHAT_MODEL_ID", "").strip(),
    }
