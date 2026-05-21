import os

from tools.aws.scope_shared.core.resource_names import (
    get_proj_prefix,
    is_project_resource_name,
    tf_state_bucket,
)


def test_get_proj_prefix_default(monkeypatch):
    monkeypatch.delenv("PROJ_PREFIX", raising=False)
    monkeypatch.delenv("FRU_PREFIX", raising=False)
    assert get_proj_prefix() == "fru"


def test_tf_state_bucket_shape(monkeypatch):
    monkeypatch.setenv("PROJ_PREFIX", "fru")
    name = tf_state_bucket("dev", "us-east-1", "123456789012")
    assert name.startswith("fru-tf-state-dev-us-east-1-123456789012")


def test_is_project_resource_name_ecr(monkeypatch):
    monkeypatch.setenv("PROJ_PREFIX", "fru")
    monkeypatch.setenv("FRU_ENV", "dev")
    repo = "fru-api-img-dev"
    assert is_project_resource_name(repo, "ecr", "dev", "us-east-1")
