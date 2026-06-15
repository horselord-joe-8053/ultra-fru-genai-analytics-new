"""
Load model catalog (embeddings + chat choices) from config/model_profiles.yaml.

Used by GET /model-catalog, per-request /query/stream overrides, and doctor checks.
Secrets resolve via .env keys named in each profile's model_env field.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.env_utils.cloud_shared.embedding_profiles import (
    EmbeddingProfile,
    _parse_profile,
    validate_profile,
)
from backend.utils.env_helpers import get_optional_env

_POPULATION_THRESHOLD = 0.95


@dataclass(frozen=True)
class ChatProfile:
    name: str
    inference: str
    model_env: str
    display: str


@dataclass(frozen=True)
class RequestModelContext:
    embedding_profile: str
    chat_choice: str
    embedding_display: str
    chat_display: str


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    container_app = here.parents[3]
    if (container_app / "config" / "model_profiles.yaml").is_file():
        return container_app
    return here.parents[4]


def default_model_profiles_path() -> Path:
    override = os.environ.get("MODEL_PROFILES_CONFIG", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "config" / "model_profiles.yaml"


@lru_cache(maxsize=1)
def _load_raw_catalog() -> dict[str, Any]:
    path = default_model_profiles_path()
    if not path.is_file():
        raise FileNotFoundError(f"Model profiles config not found: {path}")
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Model profiles YAML must be a mapping: {path}")
    return data


def get_embedding_profiles_dict() -> dict[str, EmbeddingProfile]:
    raw = _load_raw_catalog().get("embeddings") or {}
    profiles: dict[str, EmbeddingProfile] = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            raise ValueError(f"Embedding profile {name}: expected mapping")
        profiles[name] = _parse_profile(name, body)
    return profiles


def get_chat_profiles_dict() -> dict[str, ChatProfile]:
    raw = _load_raw_catalog().get("chat") or {}
    profiles: dict[str, ChatProfile] = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            raise ValueError(f"Chat profile {name}: expected mapping")
        profiles[name] = ChatProfile(
            name=name,
            inference=str(body["inference"]).strip().lower(),
            model_env=str(body["model_env"]).strip(),
            display=str(body.get("display") or name),
        )
    return profiles


def get_default_embedding_profile_name() -> str:
    legacy = get_optional_env("EMBEDDING_ACTIVE_PROFILE", "")
    return (
        get_optional_env("DEFAULT_EMBEDDING_PROFILE", "")
        or legacy
        or "openai_1536"
    ).strip() or "openai_1536"


def get_default_chat_choice_name() -> str:
    legacy_provider = get_optional_env("LLM_INFERENCE_PROVIDER", "").strip().lower()
    if legacy_provider == "modelark":
        legacy = "seed_lite"
    else:
        legacy = "claude_haiku"
    return (get_optional_env("DEFAULT_CHAT_CHOICE", "") or legacy).strip() or legacy


def _env_present(key: str) -> bool:
    return bool(get_optional_env(key, "").strip())


def profile_has_credentials(profile: EmbeddingProfile) -> bool:
    return _env_present(profile.model_env)


def chat_has_credentials(profile: ChatProfile) -> bool:
    if profile.inference == "modelark":
        return _env_present("ARK_API_KEY") and _env_present(profile.model_env)
    if profile.inference == "claude":
        cloud = get_optional_env("CLOUD_PROVIDER", "").strip().lower()
        if cloud == "gcp":
            return _env_present("GOOGLE_AI_API_KEY") or _env_present("CLAUDE_API_KEY")
        if cloud == "aws":
            return _env_present("AWS_BEDROCK_INFERENCE_PROFILE_ID") or _env_present(
                "AWS_BEDROCK_MODEL_ID"
            ) or _env_present("CLAUDE_API_KEY")
        return _env_present("CLAUDE_API_KEY")
    return False


def embedding_column_population_pct(profile_name: str, conn) -> float:
    from backend.services.embedding_sync import embedding_column_population_counts

    profiles = get_embedding_profiles_dict()
    if profile_name not in profiles:
        return 0.0
    col = profiles[profile_name].pgvector_column
    counts = embedding_column_population_counts(conn)
    total = counts.get("total_rows", 0)
    populated = counts.get(profile_name, 0)
    if not total:
        return 1.0 if populated else 0.0
    return populated / total


def embedding_profile_enabled(profile_name: str, conn=None) -> bool:
    profiles = get_embedding_profiles_dict()
    if profile_name not in profiles:
        return False
    if not profile_has_credentials(profiles[profile_name]):
        return False
    if conn is None:
        return True
    return embedding_column_population_pct(profile_name, conn) >= _POPULATION_THRESHOLD


def chat_choice_enabled(choice_name: str) -> bool:
    profiles = get_chat_profiles_dict()
    if choice_name not in profiles:
        return False
    return chat_has_credentials(profiles[choice_name])


def resolve_chat_display(choice_name: str) -> str:
    profiles = get_chat_profiles_dict()
    if choice_name not in profiles:
        return choice_name
    prof = profiles[choice_name]
    model_id = get_optional_env(prof.model_env, prof.display)
    return model_id or prof.display


def resolve_embedding_display(profile_name: str) -> str:
    from backend.env_utils.cloud_shared.embedding_profiles import resolve_model_id

    profiles = get_embedding_profiles_dict()
    if profile_name not in profiles:
        return profile_name
    try:
        return resolve_model_id(profiles[profile_name])
    except Exception:
        return profile_name


def build_model_catalog(conn=None) -> dict[str, Any]:
    embed_profiles = get_embedding_profiles_dict()
    chat_profiles = get_chat_profiles_dict()
    embeddings = []
    for pid, prof in embed_profiles.items():
        validate_profile(prof)
        populated_pct = None
        enabled = profile_has_credentials(prof)
        if conn is not None:
            populated_pct = round(embedding_column_population_pct(pid, conn) * 100, 1)
            enabled = enabled and populated_pct >= _POPULATION_THRESHOLD * 100
        embeddings.append(
            {
                "id": pid,
                "display": resolve_embedding_display(pid),
                "enabled": enabled,
                "populated_pct": populated_pct,
            }
        )
    chat = [
        {
            "id": cid,
            "display": resolve_chat_display(cid),
            "enabled": chat_choice_enabled(cid),
        }
        for cid in chat_profiles
    ]
    return {
        "embeddings": embeddings,
        "chat": chat,
        "defaults": {
            "embedding_profile": get_default_embedding_profile_name(),
            "chat_choice": get_default_chat_choice_name(),
        },
    }


def validate_model_catalog_defaults() -> list[str]:
    """Doctor: ensure default embedding/chat choices exist and have credentials."""
    errors: list[str] = []
    embed_default = get_default_embedding_profile_name()
    chat_default = get_default_chat_choice_name()
    embed_profiles = get_embedding_profiles_dict()
    chat_profiles = get_chat_profiles_dict()
    if embed_default not in embed_profiles:
        errors.append(
            f"DEFAULT_EMBEDDING_PROFILE={embed_default!r} is not in config/model_profiles.yaml"
        )
    elif not profile_has_credentials(embed_profiles[embed_default]):
        errors.append(
            f"Default embedding profile {embed_default!r} missing env "
            f"({embed_profiles[embed_default].model_env})"
        )
    if chat_default not in chat_profiles:
        errors.append(
            f"DEFAULT_CHAT_CHOICE={chat_default!r} is not in config/model_profiles.yaml"
        )
    elif not chat_has_credentials(chat_profiles[chat_default]):
        errors.append(
            f"Default chat choice {chat_default!r} is not configured for this environment"
        )
    return errors


def resolve_request_model_context(
    embedding_profile: str | None,
    chat_choice: str | None,
    *,
    allow_override: bool | None = None,
) -> RequestModelContext:
    if allow_override is None:
        allow_override = get_optional_env("ALLOW_PER_REQUEST_MODEL_OVERRIDE", "true").lower() in (
            "1",
            "true",
            "yes",
        )
    embed_name = (embedding_profile or get_default_embedding_profile_name()).strip()
    chat_name = (chat_choice or get_default_chat_choice_name()).strip()
    embed_profiles = get_embedding_profiles_dict()
    chat_profiles = get_chat_profiles_dict()
    if embed_name not in embed_profiles:
        raise ValueError(f"Unknown embedding_profile={embed_name!r}")
    if chat_name not in chat_profiles:
        raise ValueError(f"Unknown chat_choice={chat_name!r}")
    if (embedding_profile or chat_choice) and not allow_override:
        raise PermissionError("Per-request model override is disabled")
    if not profile_has_credentials(embed_profiles[embed_name]):
        raise ValueError(f"Embedding profile {embed_name!r} is not configured (missing creds)")
    if not chat_has_credentials(chat_profiles[chat_name]):
        raise ValueError(f"Chat choice {chat_name!r} is not configured (missing creds)")
    return RequestModelContext(
        embedding_profile=embed_name,
        chat_choice=chat_name,
        embedding_display=resolve_embedding_display(embed_name),
        chat_display=resolve_chat_display(chat_name),
    )
