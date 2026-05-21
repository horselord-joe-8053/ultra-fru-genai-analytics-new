import os

import pytest

from tools.cloud_shared.env import EnvVarNotFound, get_int_env, require


def test_require_present(monkeypatch):
    monkeypatch.setenv("CLOUD_TEST", "x")
    assert require("CLOUD_TEST") == "x"


def test_require_raises(monkeypatch):
    monkeypatch.delenv("CLOUD_MISSING", raising=False)
    with pytest.raises(EnvVarNotFound):
        require("CLOUD_MISSING")


def test_get_int_env_default(monkeypatch):
    monkeypatch.delenv("CLOUD_INT", raising=False)
    assert get_int_env("CLOUD_INT", 9) == 9


def test_get_int_env_parsed(monkeypatch):
    monkeypatch.setenv("CLOUD_INT", "7")
    assert get_int_env("CLOUD_INT", 0) == 7
