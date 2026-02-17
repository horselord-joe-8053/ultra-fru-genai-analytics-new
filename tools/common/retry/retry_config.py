"""
Load retry configuration from config/retry_config.json.
Overridable via FRU_RETRY_CONFIG_PATH env var.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RetriableRule:
    id: str
    pattern: str
    max_retries: int
    wait_sec: int
    regex: bool = False


@dataclass
class RetryConfig:
    retriable: list[RetriableRule]
    non_retriable: list[str]


def _default_config_path() -> Path:
    root = os.getenv("REPO_ROOT") or os.getcwd()
    return Path(root) / "config" / "retry_config.json"


def get_retry_config(config_path: str | Path | None = None) -> RetryConfig:
    """
    Load retry config. Path from FRU_RETRY_CONFIG_PATH or default config/retry_config.json.
    Returns empty config if file missing.
    """
    path = config_path or os.getenv("FRU_RETRY_CONFIG_PATH")
    if path:
        path = Path(path)
    else:
        path = _default_config_path()

    if not path.exists():
        return RetryConfig(retriable=[], non_retriable=[])

    with open(path) as f:
        data = json.load(f)

    retriable = [
        RetriableRule(
            id=r.get("id", ""),
            pattern=r["pattern"],
            max_retries=r.get("max_retries", 1),
            wait_sec=r.get("wait_sec", 60),
            regex=r.get("regex", False),
        )
        for r in data.get("retriable", [])
    ]
    non_retriable = data.get("non_retriable", [])
    return RetryConfig(retriable=retriable, non_retriable=non_retriable)
