import json
from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.byteplus.modelark_client import ModelArkClient


def test_modelark_complete_parses_response(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "k")
    monkeypatch.setenv("ARK_CHAT_MODEL_ID", "ep-chat")
    payload = {
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }

    def fake_urlopen(req, timeout=120):
        resp = MagicMock()
        resp.read.return_value = json.dumps(payload).encode()
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", fake_urlopen):
        client = ModelArkClient()
        out = client.complete("sys", "user")
    assert out["text"] == "hello"
    assert out["tokens"]["total"] == 3
