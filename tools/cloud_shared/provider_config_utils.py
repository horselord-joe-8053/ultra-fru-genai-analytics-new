"""
Shared deploy config loader. Loads config/cloud/{provider}_deploy_config.yaml.
Scope-based structure: scope_default | kube | nonkube, each with regional_default + region overrides.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Repo root: tools/cloud_shared/provider_config_utils.py -> ../ -> tools -> ../ -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config" / "cloud"

# Cache: (provider, scope, region) -> merged config dict.
_config_cache: dict[tuple[str, str, str], dict] = {}
_raw_cache: dict[str, dict] = {}  # path -> raw YAML


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _require(cfg: dict, path: str, key: str) -> object:
    """Fail-fast: raise ValueError if key missing. path is for error message (e.g. 'scope_default.network')."""
    val = cfg.get(key)
    if val is None:
        raise ValueError(f"Required key '{path}.{key}' is missing in deploy config.")
    return val


def _load_raw(provider: str) -> dict:
    """Load raw YAML. Cached per provider."""
    if provider not in _raw_cache:
        path = _CONFIG_DIR / f"{provider}_deploy_config.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Deploy config not found: {path}")
        with open(path) as f:
            _raw_cache[provider] = yaml.safe_load(f) or {}
    return _raw_cache[provider]


def load_scope_config(provider: str, scope: str, region: str) -> dict:
    """
    Load merged config for provider, scope, and region.
    Merges scope.regional_default with scope[region]. Region must exist in scope_default.
    Uses in-memory cache.
    """
    key = (provider, scope, region)
    if key not in _config_cache:
        data = _load_raw(provider)
        scope_default = data.get("scope_default", {})
        if not scope_default:
            raise ValueError(
                f"scope_default block required in {_CONFIG_DIR / f'{provider}_deploy_config.yaml'}"
            )
        # Region must exist in scope_default (for network)
        known_regions = [k for k in scope_default if k != "regional_default"]
        if region not in scope_default:
            raise ValueError(
                f"Region '{region}' not in scope_default. "
                f"Add '{region}' under scope_default. Known: {known_regions}"
            )
        scope_block = data.get(scope)
        if scope_block is None:
            raise ValueError(
                f"Scope '{scope}' not in deploy config. Expected: scope_default, kube, or nonkube."
            )
        reg_default = scope_block.get("regional_default", {})
        region_block = scope_block.get(region, {})
        _config_cache[key] = deep_merge(reg_default, region_block)
    return _config_cache[key]


def load_deploy_config(provider: str, region: str) -> dict:
    """
    Legacy: Load merged config for provider and region from scope_default.
    Kept for backward compat. Prefer load_scope_config(provider, scope, region).
    """
    return load_scope_config(provider, "scope_default", region)


def clear_config_cache() -> None:
    """Clear cache (e.g. for tests or when config file changed mid-run)."""
    _config_cache.clear()
    _raw_cache.clear()
