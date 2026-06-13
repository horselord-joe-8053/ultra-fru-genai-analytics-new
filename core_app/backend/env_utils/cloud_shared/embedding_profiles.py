"""
Load and validate embedding profiles from config/embedding_profiles.yaml.

EMBEDDING_ACTIVE_PROFILE selects the search/read lane only (semantic ANN column).
All profile columns are write targets via embedding_sync (never gated by active profile).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ALLOWED_PROVIDERS = frozenset({"openai", "modelark"})
_COLUMN_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class EmbeddingProfile:
    name: str
    provider: str
    model_slug: str
    model_env: str
    dimension: int
    pgvector_column: str

    def expected_column_name(self) -> str:
        return f"embedding_{self.model_slug}_{self.dimension}"


def _repo_root() -> Path:
    """Repo root in dev; /app in API container (config mounted at /app/config)."""
    here = Path(__file__).resolve()
    container_app = here.parents[3]  # .../backend/env_utils/cloud_shared -> /app
    if (container_app / "config" / "embedding_profiles.yaml").is_file():
        return container_app
    return here.parents[4]  # dev: fru-genai-analytics-new


def default_profiles_path() -> Path:
    override = os.environ.get("EMBEDDING_PROFILES_CONFIG", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "config" / "embedding_profiles.yaml"


def validate_profile(profile: EmbeddingProfile) -> None:
    if profile.provider not in _ALLOWED_PROVIDERS:
        raise ValueError(f"Profile {profile.name}: unsupported provider {profile.provider!r}")
    if profile.dimension <= 0:
        raise ValueError(f"Profile {profile.name}: dimension must be positive")
    if not _COLUMN_RE.match(profile.pgvector_column):
        raise ValueError(f"Profile {profile.name}: invalid pgvector_column {profile.pgvector_column!r}")
    if profile.pgvector_column != profile.expected_column_name():
        raise ValueError(
            f"Profile {profile.name}: pgvector_column must be {profile.expected_column_name()!r}, "
            f"got {profile.pgvector_column!r}"
        )


def _parse_profile(name: str, raw: dict[str, Any]) -> EmbeddingProfile:
    profile = EmbeddingProfile(
        name=name,
        provider=str(raw["provider"]).strip().lower(),
        model_slug=str(raw["model_slug"]).strip().lower(),
        model_env=str(raw["model_env"]).strip(),
        dimension=int(raw["dimension"]),
        pgvector_column=str(raw["pgvector_column"]).strip(),
    )
    validate_profile(profile)
    return profile


def load_profiles(path: Path | None = None) -> dict[str, EmbeddingProfile]:
    cfg_path = path or default_profiles_path()
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Embedding profiles config not found: {cfg_path}")
    with cfg_path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Embedding profiles YAML must be a mapping: {cfg_path}")
    profiles: dict[str, EmbeddingProfile] = {}
    for name, raw in data.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Profile {name}: expected mapping")
        profiles[name] = _parse_profile(name, raw)
    return profiles


@lru_cache(maxsize=1)
def get_profiles() -> dict[str, EmbeddingProfile]:
    return load_profiles()


def get_active_profile_name() -> str:
    return os.environ.get("EMBEDDING_ACTIVE_PROFILE", "openai_1536").strip() or "openai_1536"


def get_active_profile() -> EmbeddingProfile:
    name = get_active_profile_name()
    profiles = get_profiles()
    if name not in profiles:
        known = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown EMBEDDING_ACTIVE_PROFILE={name!r}; known: {known}")
    return profiles[name]


def get_active_pgvector_column() -> str:
    return get_active_profile().pgvector_column


def is_embedding_column(column_name: str) -> bool:
    """True for legacy `embedding` or profile columns `embedding_*`."""
    return column_name == "embedding" or column_name.startswith("embedding_")


def resolve_model_id(profile: EmbeddingProfile) -> str:
    from backend.utils.env_helpers import get_required_env

    return get_required_env(profile.model_env, f"embedding model for profile {profile.name}")
