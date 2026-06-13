"""
Shared dual-profile embedding sync orchestration (transport-agnostic).

Profile loop + embed API calls live here. psycopg2 and RDS Data API adapters
supply row fetch and vector write callbacks. Never reads EMBEDDING_ACTIVE_PROFILE.
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from openai import OpenAI

from backend.env_utils.cloud_shared.embedding_factory import create_embedding_client
from backend.env_utils.cloud_shared.embedding_profiles import EmbeddingProfile, get_profiles

logger = logging.getLogger(__name__)

_PROGRESS_INTERVAL = 25

WriteVectorFn = Callable[[EmbeddingProfile, str, list[float]], None]


@dataclass
class SyncResult:
    embedded: int = 0
    skipped: int = 0
    failed: int = 0
    per_profile: dict[str, dict[str, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _env_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def profile_has_credentials(profile: EmbeddingProfile) -> bool:
    if profile.provider == "openai":
        return _env_set("OPENAI_API_KEY")
    if profile.provider == "modelark":
        return _env_set("ARK_API_KEY") and _env_set(profile.model_env)
    return False


def available_profiles(profile_names: list[str] | None = None) -> list[EmbeddingProfile]:
    """Profiles from YAML that have credentials in the current environment."""
    all_profiles = get_profiles()
    names = profile_names or list(all_profiles.keys())
    result: list[EmbeddingProfile] = []
    for name in names:
        if name not in all_profiles:
            logger.warning("Unknown embedding profile %r; skipping", name)
            continue
        prof = all_profiles[name]
        if profile_has_credentials(prof):
            result.append(prof)
        else:
            logger.warning(
                "Skipping profile %s (%s): credentials not configured",
                prof.name,
                prof.provider,
            )
    return result


def sync_embeddings_core(
    ids: list[str],
    row_map: dict[str, tuple[str, dict[str, Any]]],
    *,
    profiles: list[str] | None = None,
    force: bool = False,
    openai_client: OpenAI | None = None,
    write_vector: WriteVectorFn,
) -> SyncResult:
    """Embed customer_feedback for given ids across all available profiles."""
    result = SyncResult()
    target_profiles = available_profiles(profiles)
    if not target_profiles:
        result.warnings.append("No embedding profiles with credentials available")
        return result

    shared_openai = openai_client or OpenAI()

    for prof in target_profiles:
        result.per_profile[prof.name] = {"embedded": 0, "skipped": 0, "failed": 0}
        client = None
        profile_start = time.monotonic()

        logger.info(
            "embedding_sync: profile=%s provider=%s column=%s rows=%d force=%s",
            prof.name,
            prof.provider,
            prof.pgvector_column,
            len(ids),
            force,
        )

        for idx, rid in enumerate(ids, start=1):
            if rid not in row_map:
                msg = f"Row {rid} not found in fru_sales_embeddings"
                result.errors.append(msg)
                result.failed += 1
                result.per_profile[prof.name]["failed"] += 1
                continue

            feedback, existing = row_map[rid]
            if not force and existing.get(prof.pgvector_column) is not None:
                result.skipped += 1
                result.per_profile[prof.name]["skipped"] += 1
                continue

            if client is None:
                try:
                    client = create_embedding_client(
                        profile=prof,
                        openai_client=shared_openai if prof.provider == "openai" else None,
                    )
                except Exception as e:
                    msg = f"Profile {prof.name}: client init failed: {e}"
                    logger.warning(msg)
                    result.warnings.append(msg)
                    result.per_profile[prof.name]["failed"] += len(ids)
                    result.failed += len(ids)
                    result.errors.append(msg)
                    break

            try:
                t0 = time.monotonic()
                vector = client.embed_texts([feedback])[0]
                elapsed_ms = int((time.monotonic() - t0) * 1000)
            except Exception as e:
                msg = f"Profile {prof.name} id {rid}: embed failed: {e}"
                logger.warning(msg)
                result.errors.append(msg)
                result.failed += 1
                result.per_profile[prof.name]["failed"] += 1
                continue

            try:
                write_vector(prof, rid, vector)
            except Exception as e:
                msg = f"Profile {prof.name} id {rid}: write failed: {e}"
                logger.warning(msg)
                result.errors.append(msg)
                result.failed += 1
                result.per_profile[prof.name]["failed"] += 1
                continue

            result.embedded += 1
            result.per_profile[prof.name]["embedded"] += 1
            existing[prof.pgvector_column] = vector

            if idx == 1 or idx % _PROGRESS_INTERVAL == 0 or idx == len(ids):
                logger.info(
                    "embedding_sync: profile=%s progress=%d/%d last_id=%s dim=%d embed_ms=%d "
                    "embedded=%d failed=%d",
                    prof.name,
                    idx,
                    len(ids),
                    rid,
                    len(vector),
                    elapsed_ms,
                    result.per_profile[prof.name]["embedded"],
                    result.per_profile[prof.name]["failed"],
                )

        logger.info(
            "embedding_sync: profile=%s done embedded=%d skipped=%d failed=%d elapsed_s=%.1f",
            prof.name,
            result.per_profile[prof.name]["embedded"],
            result.per_profile[prof.name]["skipped"],
            result.per_profile[prof.name]["failed"],
            time.monotonic() - profile_start,
        )

    return result
