import pytest

from tools.cloud_shared.analytics_schedule import (
    get_required_analytics_scheduler_interval_seconds,
    seconds_to_cron,
    seconds_to_eventbridge_rate,
)
from tools.cloud_shared.env import EnvVarNotFound


def test_interval_required(monkeypatch):
    monkeypatch.delenv("ANALYTICS_SCHEDULER_INTERVAL_SECONDS", raising=False)
    with pytest.raises(EnvVarNotFound):
        get_required_analytics_scheduler_interval_seconds()


def test_interval_too_small(monkeypatch):
    monkeypatch.setenv("ANALYTICS_SCHEDULER_INTERVAL_SECONDS", "30")
    with pytest.raises(ValueError, match=">= 60"):
        get_required_analytics_scheduler_interval_seconds()


def test_seconds_to_cron_and_eventbridge(monkeypatch):
    monkeypatch.setenv("ANALYTICS_SCHEDULER_INTERVAL_SECONDS", "180")
    assert get_required_analytics_scheduler_interval_seconds() == 180
    assert seconds_to_cron(180) == "*/3 * * * *"
    assert seconds_to_eventbridge_rate(180) == "rate(3 minutes)"
