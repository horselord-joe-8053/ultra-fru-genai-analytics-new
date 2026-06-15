"""
Integration: live embedding API smoke for OpenAI + ModelArk profiles.

Requires OPENAI_API_KEY and ARK_API_KEY + ARK_EMBEDDING_MODEL_ID in .env.
Skip in CI unit gate (pytest -m "not integration").
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


def _require_openai():
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        pytest.skip("OPENAI_API_KEY not set")


def _require_modelark():
    if not os.environ.get("ARK_API_KEY", "").strip():
        pytest.skip("ARK_API_KEY not set")
    if not os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip():
        pytest.skip("ARK_EMBEDDING_MODEL_ID not set")


def test_openai_1536_returns_valid_vector():
    _require_openai()
    prof = get_profiles()["openai_1536"]
    client = create_embedding_client(profile=prof)
    vectors = client.embed_texts(["Customer complained about loud compressor noise."])
    assert len(vectors) == 1
    assert len(vectors[0]) == prof.dimension
    assert any(abs(x) > 1e-6 for x in vectors[0])


def test_skylark_2048_returns_valid_vector():
    _require_modelark()
    prof = get_profiles()["skylark_2048"]
    client = create_embedding_client(profile=prof)
    vectors = client.embed_texts(["Customer complained about loud compressor noise."])
    assert len(vectors) == 1
    assert len(vectors[0]) == prof.dimension
    assert any(abs(x) > 1e-6 for x in vectors[0])


def test_both_profiles_in_one_session():
    """Sanity: both providers work in the same process (dual-column bootstrap path)."""
    _require_openai()
    _require_modelark()
    sample = "Freezer door seal failed after two weeks."
    for name in ("openai_1536", "skylark_2048"):
        prof = get_profiles()[name]
        client = create_embedding_client(profile=prof)
        vec = client.embed_texts([sample])[0]
        assert len(vec) == prof.dimension, f"{name}: dim {len(vec)} != {prof.dimension}"
