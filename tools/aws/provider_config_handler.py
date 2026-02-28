"""
AWS deploy config handler. Uses shared loader (tools/cloud_shared/provider_config_utils.py)
to load config/cloud/aws_deploy_config.yaml. Returns region-specific settings (AZs,
subnet CIDRs, compute, database). Config is cached per region to avoid repeated I/O.
"""
from __future__ import annotations

from pathlib import Path

from tools.cloud_shared.provider_config_utils import load_deploy_config

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "cloud" / "aws_deploy_config.yaml"


def get_config(region: str) -> dict:
    """Get merged config for region. Cached after first load."""
    return load_deploy_config("aws", region)


def get_azs(region: str) -> list[str]:
    """Return AZ list for VPC subnets and EKS."""
    cfg = get_config(region)
    azs = cfg.get("network", {}).get("azs")
    if not azs:
        raise ValueError(
            f"network.azs required for region '{region}' in {_CONFIG_PATH}"
        )
    return list(azs)


def get_subnet_cidrs(region: str) -> tuple[list[str], list[str]]:
    """Return (public_subnet_cidrs, private_subnet_cidrs)."""
    cfg = get_config(region)
    net = cfg.get("network", {})
    public = net.get("public_subnet_cidrs")
    private = net.get("private_subnet_cidrs")
    if not public or not private:
        raise ValueError(
            f"network.public_subnet_cidrs and network.private_subnet_cidrs "
            f"required for region '{region}' in {_CONFIG_PATH}"
        )
    return list(public), list(private)


def get_compute_config(region: str) -> dict:
    """Return compute section (desired_nodes, etc.)."""
    return get_config(region).get("compute", {})


def get_database_config(region: str) -> dict:
    """Return database section (multi_az, etc.)."""
    return get_config(region).get("database", {})
