"""Unit: nonkube compose passes ModelArk env from .env into API container."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_PATH = REPO_ROOT / "tools/local/docker/docker-compose.nonkube.yml"

REQUIRED_KEYS = {
    "EMBEDDING_ACTIVE_PROFILE",
    "ARK_API_KEY",
    "ARK_BASE_URL",
    "ARK_EMBEDDING_MODEL_ID",
    "ARK_CHAT_MODEL_ID",
}


def test_nonkube_compose_declares_modelark_env():
    with COMPOSE_PATH.open() as f:
        data = yaml.safe_load(f)
    env = data["services"]["api"]["environment"]
    assert REQUIRED_KEYS.issubset(set(env.keys()))
    assert "${EMBEDDING_ACTIVE_PROFILE" in env["EMBEDDING_ACTIVE_PROFILE"]
    assert "${ARK_API_KEY" in env["ARK_API_KEY"]
