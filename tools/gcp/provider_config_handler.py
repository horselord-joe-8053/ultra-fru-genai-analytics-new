"""
GCP deploy config handler. Uses shared loader (tools/cloud_shared/provider_config_utils.py)
to load config/cloud/gcp_deploy_config.yaml. Returns region-specific settings (zones,
GKE location, compute, database). Config is cached per region to avoid repeated I/O.
"""
from __future__ import annotations

from pathlib import Path

from tools.cloud_shared.provider_config_utils import load_deploy_config

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "cloud" / "gcp_deploy_config.yaml"


def get_config(region: str) -> dict:
    """Get merged config for region. Cached after first load."""
    return load_deploy_config("gcp", region)


def get_gke_location(region: str) -> str:
    """
    Return GKE cluster location: zone (e.g. us-central1-a) for zonal,
    or region (e.g. us-central1) for regional.
    """
    cfg = get_config(region)
    compute = cfg.get("compute", {})
    loc_type = compute.get("location_type", "zonal")
    if loc_type == "zonal":
        zone = compute.get("zone")
        if not zone:
            raise ValueError(
                f"compute.zone required when location_type=zonal "
                f"for region '{region}' in {_CONFIG_PATH}"
            )
        return zone
    return region


def get_initial_node_count(region: str) -> int:
    """Return GKE initial_node_count."""
    cfg = get_config(region)
    return int(cfg.get("compute", {}).get("initial_node_count", 1))


def get_compute_config(region: str) -> dict:
    """Return compute section (location_type, zone, initial_node_count)."""
    return get_config(region).get("compute", {})


def get_database_config(region: str) -> dict:
    """Return database section (high_availability, etc.)."""
    return get_config(region).get("database", {})
