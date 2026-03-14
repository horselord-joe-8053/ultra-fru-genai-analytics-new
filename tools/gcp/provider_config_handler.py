"""
GCP deploy config handler. Uses shared loader (tools/cloud_shared/provider_config_utils.py)
to load config/cloud/gcp_deploy_config.yaml. Returns scope-specific settings.
"""
from __future__ import annotations

from pathlib import Path

from tools.cloud_shared.provider_config_utils import load_scope_config, _require

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "cloud" / "gcp_deploy_config.yaml"


def get_network_config(region: str) -> dict:
    """Return network config from scope_default."""
    cfg = load_scope_config("gcp", "scope_default", region)
    return cfg.get("network", {})


def get_database_config(region: str) -> dict:
    """Return database config from scope_default."""
    cfg = load_scope_config("gcp", "scope_default", region)
    return cfg.get("database", {})


def get_gke_location(region: str) -> str:
    """
    Return GKE cluster location: zone (e.g. us-central1-a) for zonal,
    or region (e.g. us-central1) for regional.
    """
    comp = get_kube_compute_config(region)
    loc_type = comp.get("location_type", "zonal")
    if loc_type == "zonal":
        zone = comp.get("zone")
        if not zone:
            raise ValueError(
                f"compute.zone required when location_type=zonal "
                f"for region '{region}' in {_CONFIG_PATH}"
            )
        return zone
    return region


def get_kube_compute_config(region: str) -> dict:
    """Return GKE compute config from kube scope. Fail-fast on required keys."""
    cfg = load_scope_config("gcp", "kube", region)
    comp = cfg.get("compute", {})
    _require(comp, "kube.compute", "location_type")
    _require(comp, "kube.compute", "min_node_count")
    _require(comp, "kube.compute", "max_node_count")
    _require(comp, "kube.compute", "machine_type")
    return comp


def get_nonkube_compute_config(region: str) -> dict:
    """Return Cloud Run compute config from nonkube scope. Fail-fast on required keys."""
    cfg = load_scope_config("gcp", "nonkube", region)
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
    """Legacy: merged scope_default config."""
    return load_scope_config("gcp", "scope_default", region)


def get_compute_config(region: str) -> dict:
    """Deprecated: Use get_kube_compute_config or get_nonkube_compute_config."""
    return get_config(region).get("compute", {})


def get_initial_node_count(region: str) -> int:
    """Deprecated: Use get_kube_compute_config(region)['min_node_count']."""
    return int(get_kube_compute_config(region).get("min_node_count", 1))
