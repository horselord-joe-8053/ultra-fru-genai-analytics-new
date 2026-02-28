"""
Shared deploy config loader. Loads config/cloud/{provider}_deploy_config.yaml,
merges default + region block, and caches per (provider, region) to avoid
repeated file I/O during a deploy run.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Repo root: tools/cloud_shared/provider_config_utils.py -> ../ -> tools -> ../ -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config" / "cloud"

# Cache: (provider, region) -> merged config dict. Cleared on process exit.
_config_cache: dict[tuple[str, str], dict] = {}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_deploy_config(provider: str, region: str) -> dict:
    """
    Load merged config for provider and region.
    Uses in-memory cache: first call reads file; subsequent calls return cached.
    """
    key = (provider, region)
    if key not in _config_cache:
        path = _CONFIG_DIR / f"{provider}_deploy_config.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Deploy config not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        default = data.get("default", {})
        region_block = data.get(region)
        if region_block is None:
            raise ValueError(
                f"Region '{region}' not in {path}. "
                f"Add a '{region}' block or use a configured region."
            )
        _config_cache[key] = deep_merge(default, region_block)
    return _config_cache[key]


def clear_config_cache() -> None:
    """Clear cache (e.g. for tests or when config file changed mid-run)."""
    _config_cache.clear()
