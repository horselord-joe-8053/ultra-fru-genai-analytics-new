"""Shared pytest fixtures: repo paths, env defaults, Flask app client."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_APP = REPO_ROOT / "core_app"

# Import paths before any backend modules load.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(CORE_APP) not in sys.path:
    sys.path.insert(0, str(CORE_APP))

os.environ.setdefault("REPO_ROOT", str(REPO_ROOT))

_MIN_APP_ENV = {
    "LOG_LEVEL": "WARNING",
    "ALLOWED_ORIGINS": "http://localhost:5173",
    "USE_AGENT_QUERY": "false",
    "PGHOST": "127.0.0.1",
    "PGPORT": "5432",
    "PGUSER": "test",
    "PGPASSWORD": "test",
    "PGDATABASE": "test",
    "OPENAI_API_KEY": "sk-test",
    "OPENAI_EMBED_MODEL": "text-embedding-3-small",
    "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": "180",
    "NUM_FOR_BATCH_ANALYTICS_TOP_QUERY": "8",
    "NUM_FOR_BATCH_ANALYTICS_TOP_SPARK_COMPUTE": "20",
}

# Set before collection imports backend.api.app.
for _k, _v in _MIN_APP_ENV.items():
    os.environ.setdefault(_k, _v)


@pytest.fixture
def app_client(monkeypatch):
    """Flask test client with DB/agent calls mocked."""
    monkeypatch.setenv("USE_AGENT_QUERY", "false")
    from backend.api import app as app_module

    with monkeypatch.context() as m:
        m.setattr(app_module, "_connection_pool", None)
        m.setattr(app_module, "query_agent", None)
        m.setattr(
            app_module,
            "get_db_conn",
            lambda: (_ for _ in ()).throw(ConnectionError("mock db down")),
        )
        yield app_module.app.test_client()


@pytest.fixture
def deploy_config_fixture_dir(tmp_path, monkeypatch):
    """Point provider_config_utils at a minimal YAML tree."""
    cfg_dir = tmp_path / "config" / "cloud"
    cfg_dir.mkdir(parents=True)
    src = REPO_ROOT / "tests" / "fixtures" / "config" / "aws_deploy_config_minimal.yaml"
    (cfg_dir / "aws_deploy_config.yaml").write_text(src.read_text())
    import tools.cloud_shared.provider_config_utils as pcu

    monkeypatch.setattr(pcu, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(pcu, "_CONFIG_DIR", cfg_dir)
    pcu.clear_config_cache()
    yield cfg_dir
    pcu.clear_config_cache()
