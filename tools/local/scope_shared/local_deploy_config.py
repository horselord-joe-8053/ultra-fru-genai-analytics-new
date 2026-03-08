"""
Load config/local/local_deploy_config.yaml for local kube/nonkube ports.

Used by start_local, verify_all_deploy, deploy (logging).
Config path: LOCAL_DEPLOY_CONFIG env (relative to project root), default config/local/local_deploy_config.yaml.
"""
from __future__ import annotations

import os
from typing import TypedDict


class LocalScopePorts(TypedDict):
    api_port: int
    frontend_port: int


def _project_root() -> str:
    """Project root (directory containing config/)."""
    here = os.path.abspath(os.path.dirname(__file__))
    # tools/local/scope_shared -> project root
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


def _load_yaml_path() -> str:
    rel = os.environ.get("LOCAL_DEPLOY_CONFIG", "config/local/local_deploy_config.yaml")
    root = _project_root()
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Local deploy config not found: {path} (set LOCAL_DEPLOY_CONFIG to override)"
        )
    return path


def get_ports_for_scope(scope: str) -> LocalScopePorts:
    """
    Return api_port and frontend_port for the given scope.
    scope: "kube" | "nonkube" | "all"
    For "all", returns nonkube ports (single frontend when starting after deploy all).
    """
    import yaml

    path = _load_yaml_path()
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    if scope == "all":
        scope = "nonkube"
    block = data.get(scope)
    if not block:
        raise KeyError(
            f"Scope '{scope}' not found in {path}; expected 'kube' and 'nonkube'"
        )
    api = int(block.get("api_port"))
    frontend = int(block.get("frontend_port"))
    if not api or not frontend:
        raise ValueError(
            f"Scope '{scope}' in {path} must define api_port and frontend_port"
        )
    return LocalScopePorts(api_port=api, frontend_port=frontend)


def get_memo_dir() -> str:
    """tools/local/memo directory for port/scope files."""
    return os.path.join(_project_root(), "tools", "local", "memo")
