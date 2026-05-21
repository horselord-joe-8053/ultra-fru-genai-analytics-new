import os

import pytest

from backend.utils.env_helpers import (
    get_optional_bool_env,
    get_optional_env,
    get_optional_int_env,
    get_required_env,
    get_required_int_env,
)


def test_get_required_env_present(monkeypatch):
    monkeypatch.setenv("TEST_REQ", "hello")
    assert get_required_env("TEST_REQ", "hint") == "hello"


def test_get_required_env_missing(monkeypatch):
    monkeypatch.delenv("TEST_REQ_MISSING", raising=False)
    with pytest.raises(ValueError, match="TEST_REQ_MISSING"):
        get_required_env("TEST_REQ_MISSING", "hint")


def test_get_optional_env_default(monkeypatch):
    monkeypatch.delenv("TEST_OPT", raising=False)
    assert get_optional_env("TEST_OPT", "fallback") == "fallback"


def test_get_optional_bool_env_truthy(monkeypatch):
    for val in ("true", "1", "yes", "on"):
        monkeypatch.setenv("TEST_BOOL", val)
        assert get_optional_bool_env("TEST_BOOL", False) is True


def test_get_optional_bool_env_falsey(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "0")
    assert get_optional_bool_env("TEST_BOOL", True) is False


def test_get_optional_int_env(monkeypatch):
    monkeypatch.setenv("TEST_INT", "42")
    assert get_optional_int_env("TEST_INT", 1) == 42


def test_get_required_int_env_invalid(monkeypatch):
    monkeypatch.setenv("TEST_RINT", "not-a-number")
    with pytest.raises(ValueError, match="integer"):
        get_required_int_env("TEST_RINT", "hint")
