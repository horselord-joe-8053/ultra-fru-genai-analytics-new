"""
Integration: ModelArk embedding profile (skylark_2048) when ARK_API_KEY is set.

Skip by default — no BytePlus credentials in CI unit gate.
"""
from __future__ import annotations

import os

import pytest

from backend.env_utils.cloud_shared.embedding_factory import create_embedding_client
from backend.env_utils.cloud_shared.embedding_profiles import get_profiles

pytestmark = [pytest.mark.integration, pytest.mark.embedding_profile]


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_modelark_embed_one_string():
    if not os.environ.get("ARK_API_KEY", "").strip():
        pytest.skip("ARK_API_KEY not set")
    os.environ.setdefault("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    os.environ.setdefault("ARK_EMBEDDING_MODEL_ID", "")
    if not os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip():
        pytest.skip("ARK_EMBEDDING_MODEL_ID not set")

    client = create_embedding_client()
    vectors = client.embed_texts(["integration smoke text"])
    assert len(vectors) == 1
    assert len(vectors[0]) == client.dimension
