"""
AWS deploy config handler. Uses shared loader (tools/cloud_shared/provider_config_utils.py)
to load config/cloud/aws_deploy_config.yaml. Returns scope-specific settings.
"""
from __future__ import annotations

from pathlib import Path

from tools.cloud_shared.provider_config_utils import load_scope_config, _require

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "cloud" / "aws_deploy_config.yaml"


def get_network_config(region: str) -> dict:
    """Return network config from scope_default. Fail-fast on missing keys."""
    cfg = load_scope_config("aws", "scope_default", region)
    net = cfg.get("network", {})
    _require(net, "scope_default.network", "azs")
    _require(net, "scope_default.network", "public_subnet_cidrs")
    _require(net, "scope_default.network", "private_subnet_cidrs")
    return net


def get_database_config(region: str) -> dict:
    """Return database config from scope_default."""
    cfg = load_scope_config("aws", "scope_default", region)
    return cfg.get("database", {})


def get_azs(region: str) -> list[str]:
    """Return AZ list for VPC subnets and EKS."""
    net = get_network_config(region)
    return list(net["azs"])


def get_subnet_cidrs(region: str) -> tuple[list[str], list[str]]:
    """Return (public_subnet_cidrs, private_subnet_cidrs)."""
    net = get_network_config(region)
    return list(net["public_subnet_cidrs"]), list(net["private_subnet_cidrs"])


def get_kube_compute_config(region: str) -> dict:
    """Return EKS compute config from kube scope. Fail-fast on missing keys."""
    cfg = load_scope_config("aws", "kube", region)
    comp = cfg.get("compute", {})
    _require(comp, "kube.compute", "min_node_count")
    _require(comp, "kube.compute", "max_node_count")
    _require(comp, "kube.compute", "node_instance_types")
    return comp


def get_nonkube_compute_config(region: str) -> dict:
    """Return ECS compute config from nonkube scope. Fail-fast on missing keys."""
    cfg = load_scope_config("aws", "nonkube", region)
    comp = cfg.get("compute", {})
    _require(comp, "nonkube.compute", "min_instance_count")
    _require(comp, "nonkube.compute", "max_instance_count")
    tasks = comp.get("tasks", {})
    _require(tasks, "nonkube.compute.tasks", "api")
    _require(tasks, "nonkube.compute.tasks", "spark")
    _require(tasks["api"], "nonkube.compute.tasks.api", "cpu")
    _require(tasks["api"], "nonkube.compute.tasks.api", "memory")
    _require(tasks["spark"], "nonkube.compute.tasks.spark", "cpu")
    _require(tasks["spark"], "nonkube.compute.tasks.spark", "memory")
    return comp


def get_config(region: str) -> dict:
    """Legacy: merged scope_default config. Prefer get_network_config, get_kube_compute_config, etc."""
    return load_scope_config("aws", "scope_default", region)


def get_compute_config(region: str) -> dict:
    """Deprecated: Use get_kube_compute_config or get_nonkube_compute_config."""
    return get_config(region).get("compute", {})
