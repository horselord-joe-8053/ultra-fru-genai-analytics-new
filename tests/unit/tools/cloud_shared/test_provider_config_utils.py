import pytest

from tools.cloud_shared import provider_config_utils as pcu


def test_deep_merge_nested():
    base = {"a": {"x": 1}, "b": 2}
    override = {"a": {"y": 2}, "b": 3}
    merged = pcu.deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 2}, "b": 3}


def test_load_scope_config(deploy_config_fixture_dir):
    cfg = pcu.load_scope_config("aws", "kube", "us-east-1")
    assert cfg["compute"]["min_node_count"] == 2


def test_load_scope_config_unknown_region(deploy_config_fixture_dir):
    with pytest.raises(ValueError, match="Region"):
        pcu.load_scope_config("aws", "kube", "eu-west-1")


def test_clear_config_cache(deploy_config_fixture_dir):
    pcu.load_scope_config("aws", "scope_default", "us-east-1")
    pcu.clear_config_cache()
    assert not pcu._config_cache
