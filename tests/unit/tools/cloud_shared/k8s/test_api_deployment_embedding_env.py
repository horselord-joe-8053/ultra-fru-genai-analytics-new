"""Unit: api-deployment.yaml.j2 includes embedding profile + ModelArk env."""
from __future__ import annotations

from tools.cloud_shared.embedding_deploy_env import api_deployment_embedding_subs
from tools.cloud_shared.k8s_j2_render import render


def _minimal_local_api_subs() -> dict:
    base = {
        "cloud_provider": "local",
        "APP_IMAGE": "fru-api:local",
        "APP_IMAGE_TAG": "local",
        "CONTAINER_TYPE": "local-kube",
        "DEPLOY_SCOPE": "kube",
        "CLOUD_PROVIDER": "local",
        "PGHOST": "host.docker.internal",
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGDATABASE": "fru_db",
        "ALLOWED_ORIGINS": "*",
        "CLOUD_REGION": "local",
        "DELTA_TABLE_PATH": "file:///tmp/delta/fru_sales",
        "DELTA_LAKE_PACKAGE": "io.delta:delta-spark_2.13:4.0.0",
        "SPARK_HOME": "/opt/spark",
        "GCP_LLM_PROVIDER": "claude",
        "CLAUDE_MODEL": "claude-haiku-4-5",
        "GOOGLE_MODEL": "gemini-2.5-flash",
        "ENABLE_ANALYTICS_SCHEDULER": "true",
        "ANALYTICS_SCHEDULER_INTERVAL_SECONDS": "180",
        "OPENAI_EMBED_MODEL": "text-embedding-3-small",
    }
    base.update(api_deployment_embedding_subs())
    return base


def test_api_deployment_renders_embedding_and_modelark_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "skylark-embed")
    monkeypatch.setenv("ARK_CHAT_MODEL_ID", "seed-lite")
    yaml_text = render("api-deployment", _minimal_local_api_subs())
    assert "name: EMBEDDING_ACTIVE_PROFILE" in yaml_text
    assert 'value: "skylark_2048"' in yaml_text
    assert "name: ARK_EMBEDDING_MODEL_ID" in yaml_text
    assert 'value: "skylark-embed"' in yaml_text
    assert "name: ARK_API_KEY" in yaml_text
    assert "secretKeyRef" in yaml_text
    assert "key: ARK_API_KEY" in yaml_text
    assert "optional: true" in yaml_text
