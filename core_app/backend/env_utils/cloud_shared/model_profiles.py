"""
Load model catalog (embeddings, chat models, stacks) from config/model_profiles.yaml.

Used by GET /model-catalog, per-request /query/stream overrides, doctor, and verify scripts.
YAML holds concrete model ids and legit (embedding, chat) pairs; API keys stay in .env only.
"""
from __future__ import annotations

import logging
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
from backend.env_utils.cloud_shared.provider import get_cloud_provider
from backend.utils.env_helpers import get_optional_env

logger = logging.getLogger(__name__)

_POPULATION_THRESHOLD = 0.95
_composites_warned = False


@dataclass(frozen=True)
class ChatProfile:
    name: str
    inference: str
    model_id: str
    display: str
    model_env: str = ""
    bedrock_model_id: str = ""
    bedrock_inference_profile_id: str = ""


@dataclass(frozen=True)
class StackEntry:
    embedding: str
    chat: str
    group: str = ""


@dataclass(frozen=True)
class StackGroup:
    name: str
    display: str
    allowed_clouds: tuple[str, ...]


@dataclass(frozen=True)
class RequestModelContext:
    embedding_profile: str
    chat_choice: str
    embedding_display: str
    chat_display: str
    chat_model_id: str


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


def clear_model_profiles_cache() -> None:
    """Test helper: reload YAML after env or file changes."""
    _load_raw_catalog.cache_clear()


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
        model_id = str(body.get("model_id") or body.get("display") or name).strip()
        profiles[name] = ChatProfile(
            name=name,
            inference=str(body["inference"]).strip().lower(),
            model_id=model_id,
            display=str(body.get("display") or model_id),
            model_env=str(body.get("model_env") or "").strip(),
            bedrock_model_id=str(body.get("bedrock_model_id") or "").strip(),
            bedrock_inference_profile_id=str(
                body.get("bedrock_inference_profile_id") or ""
            ).strip(),
        )
    return profiles


def get_stack_groups_dict() -> dict[str, StackGroup]:
    raw = _load_raw_catalog().get("stack_groups") or {}
    groups: dict[str, StackGroup] = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            continue
        clouds = body.get("allowed_clouds") or ["local", "aws", "gcp"]
        groups[name] = StackGroup(
            name=name,
            display=str(body.get("display") or name),
            allowed_clouds=tuple(str(c).strip().lower() for c in clouds),
        )
    return groups


def get_stacks_list() -> list[StackEntry]:
    raw = _load_raw_catalog()
    stacks_raw = raw.get("stacks")
    if stacks_raw:
        stacks: list[StackEntry] = []
        for item in stacks_raw:
            if not isinstance(item, dict):
                continue
            stacks.append(
                StackEntry(
                    embedding=str(item["embedding"]).strip(),
                    chat=str(item["chat"]).strip(),
                    group=str(item.get("group") or "").strip(),
                )
            )
        return stacks
    global _composites_warned
    composites = raw.get("composites") or {}
    if composites and not _composites_warned:
        logger.warning(
            "model_profiles.yaml: 'composites' is deprecated; use 'stacks' instead"
        )
        _composites_warned = True
    return [
        StackEntry(
            embedding=str(body["embedding"]).strip(),
            chat=str(body["chat"]).strip(),
        )
        for body in composites.values()
        if isinstance(body, dict)
    ]


def get_allow_per_request_override() -> bool:
    return get_optional_env("ALLOW_PER_REQUEST_MODEL_OVERRIDE", "true").lower() in (
        "1",
        "true",
        "yes",
    )


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
        return _env_present("ARK_API_KEY")
    if profile.inference == "claude":
        cloud = get_cloud_provider()
        if cloud == "gcp":
            return _env_present("CLAUDE_API_KEY") or _env_present("GOOGLE_AI_API_KEY")
        if cloud == "aws":
            return (
                _env_present("AWS_BEDROCK_INFERENCE_PROFILE_ID")
                or _env_present("AWS_BEDROCK_MODEL_ID")
                or _env_present("CLAUDE_API_KEY")
            )
        return _env_present("CLAUDE_API_KEY")
    return False


def resolve_chat_model_id(
    choice_name: str,
    cloud_provider: str | None = None,
) -> str:
    """Resolved runtime model id for planning, SQL, and synthesis."""
    profiles = get_chat_profiles_dict()
    if choice_name not in profiles:
        return choice_name
    prof = profiles[choice_name]
    cp = (cloud_provider or get_cloud_provider()).strip().lower()

    if prof.inference == "modelark":
        if prof.model_env and _env_present(prof.model_env):
            env_val = get_optional_env(prof.model_env, "").strip()
            if env_val:
                return env_val
        return prof.model_id

    if cp == "aws":
        if prof.bedrock_inference_profile_id:
            return prof.bedrock_inference_profile_id
        if prof.bedrock_model_id:
            return prof.bedrock_model_id
        return (
            get_optional_env("AWS_BEDROCK_INFERENCE_PROFILE_ID", "").strip()
            or get_optional_env("AWS_BEDROCK_MODEL_ID", "").strip()
            or prof.model_id
        )

    if prof.model_env and _env_present(prof.model_env):
        env_val = get_optional_env(prof.model_env, "").strip()
        if env_val:
            return env_val
    return prof.model_id


def resolve_chat_display(choice_name: str) -> str:
    profiles = get_chat_profiles_dict()
    if choice_name not in profiles:
        return choice_name
    return profiles[choice_name].display


def resolve_embedding_display(profile_name: str) -> str:
    from backend.env_utils.cloud_shared.embedding_profiles import resolve_model_id

    profiles = get_embedding_profiles_dict()
    if profile_name not in profiles:
        return profile_name
    try:
        return resolve_model_id(profiles[profile_name])
    except Exception:
        return profile_name


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


def _stack_allowed_on_cloud(stack: StackEntry, cloud: str) -> bool:
    if not stack.group:
        return True
    groups = get_stack_groups_dict()
    grp = groups.get(stack.group)
    if grp is None:
        return True
    return cloud in grp.allowed_clouds


def stack_enabled(stack: StackEntry, conn=None, cloud: str | None = None) -> bool:
    cp = (cloud or get_cloud_provider()).strip().lower()
    if not _stack_allowed_on_cloud(stack, cp):
        return False
    if not embedding_profile_enabled(stack.embedding, conn):
        return False
    if not chat_choice_enabled(stack.chat):
        return False
    return True


def chat_choices_for_embedding(
    embedding_profile: str,
    conn=None,
    cloud: str | None = None,
) -> list[str]:
    """Logical chat ids allowed with this embedding on this deployment."""
    seen: set[str] = set()
    out: list[str] = []
    for stack in get_stacks_list():
        if stack.embedding != embedding_profile:
            continue
        if not stack_enabled(stack, conn, cloud):
            continue
        if stack.chat not in seen:
            seen.add(stack.chat)
            out.append(stack.chat)
    return out


def embeddings_in_enabled_stacks(conn=None, cloud: str | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for stack in get_stacks_list():
        if not stack_enabled(stack, conn, cloud):
            continue
        if stack.embedding not in seen:
            seen.add(stack.embedding)
            out.append(stack.embedding)
    return out


def is_valid_stack_pair(
    embedding_profile: str,
    chat_choice: str,
    conn=None,
    cloud: str | None = None,
) -> bool:
    for stack in get_stacks_list():
        if stack.embedding == embedding_profile and stack.chat == chat_choice:
            return stack_enabled(stack, conn, cloud)
    return False


def build_model_catalog(conn=None) -> dict[str, Any]:
    embed_profiles = get_embedding_profiles_dict()
    chat_profiles = get_chat_profiles_dict()
    cloud = get_cloud_provider()
    allow_override = get_allow_per_request_override()
    enabled_embed_ids = set(embeddings_in_enabled_stacks(conn, cloud))
    enabled_chat_ids: set[str] = set()
    for eid in enabled_embed_ids:
        enabled_chat_ids.update(chat_choices_for_embedding(eid, conn, cloud))

    embeddings = []
    for pid, prof in embed_profiles.items():
        validate_profile(prof)
        populated_pct = None
        enabled = pid in enabled_embed_ids
        if conn is not None and profile_has_credentials(prof):
            populated_pct = round(embedding_column_population_pct(pid, conn) * 100, 1)
            if populated_pct < _POPULATION_THRESHOLD * 100:
                enabled = False
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
            "enabled": cid in enabled_chat_ids and chat_choice_enabled(cid),
        }
        for cid in chat_profiles
    ]

    stacks_out = []
    for stack in get_stacks_list():
        stacks_out.append(
            {
                "embedding_profile": stack.embedding,
                "chat_choice": stack.chat,
                "stack_group": stack.group or None,
                "enabled": stack_enabled(stack, conn, cloud),
            }
        )

    return {
        "cloud_provider": cloud,
        "allow_override": allow_override,
        "stacks": stacks_out,
        "embeddings": embeddings,
        "chat": chat,
        "defaults": {
            "embedding_profile": get_default_embedding_profile_name(),
            "chat_choice": get_default_chat_choice_name(),
        },
    }


def validate_model_catalog_defaults() -> list[str]:
    """Doctor: defaults exist, have creds, and form an enabled stack."""
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
    if not is_valid_stack_pair(embed_default, chat_default):
        errors.append(
            f"Default stack ({embed_default!r}, {chat_default!r}) is not an enabled "
            "combination for this cloud/credentials"
        )
    return errors


def resolve_request_model_context(
    embedding_profile: str | None,
    chat_choice: str | None,
    *,
    allow_override: bool | None = None,
    conn=None,
) -> RequestModelContext:
    if allow_override is None:
        allow_override = get_allow_per_request_override()
    embed_default = get_default_embedding_profile_name()
    chat_default = get_default_chat_choice_name()
    embed_name = (embedding_profile or embed_default).strip()
    chat_name = (chat_choice or chat_default).strip()
    embed_profiles = get_embedding_profiles_dict()
    chat_profiles = get_chat_profiles_dict()

    if embed_name not in embed_profiles:
        raise ValueError(f"Unknown embedding_profile={embed_name!r}")
    if chat_name not in chat_profiles:
        raise ValueError(f"Unknown chat_choice={chat_name!r}")

    params_differ = (embedding_profile and embedding_profile.strip() != embed_default) or (
        chat_choice and chat_choice.strip() != chat_default
    )
    if params_differ and not allow_override:
        raise PermissionError("Per-request model override is disabled")

    if not profile_has_credentials(embed_profiles[embed_name]):
        raise ValueError(f"Embedding profile {embed_name!r} is not configured (missing creds)")
    if not chat_has_credentials(chat_profiles[chat_name]):
        raise ValueError(f"Chat choice {chat_name!r} is not configured (missing creds)")
    if not is_valid_stack_pair(embed_name, chat_name, conn):
        raise ValueError(
            f"Invalid model stack: embedding_profile={embed_name!r} "
            f"chat_choice={chat_name!r} is not allowed for this deployment"
        )

    cloud = get_cloud_provider()
    chat_model_id = resolve_chat_model_id(chat_name, cloud)
    return RequestModelContext(
        embedding_profile=embed_name,
        chat_choice=chat_name,
        embedding_display=resolve_embedding_display(embed_name),
        chat_display=resolve_chat_display(chat_name),
        chat_model_id=chat_model_id,
    )
