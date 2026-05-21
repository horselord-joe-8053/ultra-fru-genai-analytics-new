"""Unit: verify_api_endpoints endpoint_names filter (no HTTP)."""
from unittest.mock import MagicMock, patch

from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints


def test_endpoint_names_limits_checks():
    resp = MagicMock(status_code=200, text='{"status":"ok"}')
    resp.json.return_value = {"status": "ok"}
    with patch("tools.cloud_shared.verify.verify_api_endpoints.requests.get", return_value=resp):
        with patch("tools.cloud_shared.verify.verify_api_endpoints.poll_until", return_value=True):
            ok, rows = verify_api_endpoints(
                "http://test",
                total_rec=0,
                scope="nonkube",
                provider="local",
                timeout_secs=1,
                endpoint_names=["Health"],
            )
    assert ok
    assert len(rows) == 1
    assert rows[0].endpoint == "Health"
