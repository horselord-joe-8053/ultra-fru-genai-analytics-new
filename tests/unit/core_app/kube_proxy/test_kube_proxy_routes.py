"""GCP kube-proxy must forward API routes used by the UI (including /model-catalog)."""

from kube_proxy.main import API_PREFIXES, _is_api_path


def test_kube_proxy_api_prefixes_include_model_catalog():
    assert "/model-catalog" in API_PREFIXES


def test_is_api_path_model_catalog():
    assert _is_api_path("/model-catalog") is True
    assert _is_api_path("/query/stream") is True
    assert _is_api_path("/assets/index.js") is False
