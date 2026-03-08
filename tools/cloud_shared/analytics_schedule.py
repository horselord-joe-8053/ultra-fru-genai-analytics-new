"""
Analytics scheduler interval: single source of truth from ANALYTICS_SCHEDULER_INTERVAL_SECONDS in .env.

All flows (local, kube, nonkube) use this. No defaults; fail-fast if missing.
"""
import os

from tools.cloud_shared.env import EnvVarNotFound


def get_required_analytics_scheduler_interval_seconds() -> int:
    """
    Require ANALYTICS_SCHEDULER_INTERVAL_SECONDS in .env. Fail-fast if missing.
    Returns int >= 60.
    """
    v = os.getenv("ANALYTICS_SCHEDULER_INTERVAL_SECONDS")
    if not v:
        raise EnvVarNotFound(
            "ANALYTICS_SCHEDULER_INTERVAL_SECONDS",
            "Add to .env (e.g. 180 for every 3 minutes). Required for analytics scheduling.",
        )
    try:
        n = int(v)
    except ValueError:
        raise ValueError(
            f"ANALYTICS_SCHEDULER_INTERVAL_SECONDS must be an integer, got: {v!r}"
        )
    if n < 60:
        raise ValueError(
            f"ANALYTICS_SCHEDULER_INTERVAL_SECONDS must be >= 60, got: {n}"
        )
    return n


def seconds_to_cron(seconds: int) -> str:
    """Convert seconds to cron for K8s CronJob and Cloud Scheduler."""
    mins = max(1, seconds // 60)
    return f"*/{mins} * * * *" if mins < 60 else "0 * * * *"


def seconds_to_eventbridge_rate(seconds: int) -> str:
    """Convert seconds to EventBridge rate() expression."""
    mins = max(1, seconds // 60)
    return f"rate({mins} minutes)" if mins < 60 else "rate(1 hour)"
