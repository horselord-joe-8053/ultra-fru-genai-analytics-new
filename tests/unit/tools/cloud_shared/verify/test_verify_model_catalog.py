"""Unit: verify_api_endpoints ModelCatalog check rejects SPA HTML."""

from unittest.mock import MagicMock, patch

import pytest

from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints


def test_model_catalog_accepts_json_stacks():
    resp = MagicMock(status_code=200)
    resp.headers = {"content-type": "application/json; charset=utf-8"}
    resp.json.return_value = {"stacks": [{"id": "openai_claude"}], "defaults": {}}
    with patch("tools.cloud_shared.verify.verify_api_endpoints.requests.get", return_value=resp):
        with patch(
            "tools.cloud_shared.verify.verify_api_endpoints.poll_until",
            side_effect=lambda fn, **kwargs: fn(),
        ):
            ok, rows = verify_api_endpoints(
                "http://test",
                total_rec=200,
                scope="kube",
                provider="gcp",
                timeout_secs=1,
                endpoint_names=["ModelCatalog"],
            )
    assert ok
    assert rows[0].endpoint == "ModelCatalog"
    assert rows[0].ok is True


def test_model_catalog_rejects_html():
    resp = MagicMock(status_code=200)
    resp.headers = {"content-type": "text/html; charset=utf-8"}
    resp.text = "<html><body>index</body></html>"
    resp.json.side_effect = ValueError("not json")

    def fake_poll(fn, **kwargs):
        fn()
        return False

    with patch("tools.cloud_shared.verify.verify_api_endpoints.requests.get", return_value=resp):
        with patch("tools.cloud_shared.verify.verify_api_endpoints.poll_until", side_effect=fake_poll):
            with pytest.raises(RuntimeError, match="expected JSON"):
                verify_api_endpoints(
                    "http://test",
                    total_rec=200,
                    scope="nonkube",
                    provider="aws",
                    timeout_secs=1,
                    endpoint_names=["ModelCatalog"],
                )
