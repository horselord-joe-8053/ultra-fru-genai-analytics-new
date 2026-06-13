"""Unit tests for AWS nonkube ECS ModelArk / embedding env in Terraform."""
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
_NONKUBE_MAIN = _REPO / "infra_terraform/live_deploy/aws/nonkube/main.tf"


def test_nonkube_main_tf_includes_ark_api_key_secret():
    source = _NONKUBE_MAIN.read_text()
    assert "ARK_API_KEY" in source
    assert "ark_api_key_secret_arn" in source


def test_nonkube_env_vars_include_ark_embedding_model_id():
    source = _NONKUBE_MAIN.read_text()
    assert "ARK_EMBEDDING_MODEL_ID" in source
    assert "ARK_BASE_URL" in source
