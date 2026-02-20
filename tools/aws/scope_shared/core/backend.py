
import os
from tools.cloud_shared.env import require, EnvVarNotFound

def stack_id_from_dir(stack_dir: str, cloud: str = "aws") -> str:
    """Extract logical stack name from path. Cloud comes from caller (tools/aws vs tools/gcp), not from path.
    Strips first path component (deploy root) without hardcoding names; rest becomes logical id.
    Backward compat: scope-shared -> shared in state key so existing tfstate remains valid.
    infra_terraform/live_deploy/{cloud}/... -> same keys as live_deploy_{cloud}/... (Option A)."""
    path = stack_dir.strip("/")
    parts = path.split("/")

    # infra_terraform/live_deploy/aws/scope_shared/durable -> extract aws/scope_shared/durable, use cloud from path
    if path.startswith("infra_terraform/live_deploy/") and len(parts) >= 4:
        path_cloud = parts[2]  # aws or gcp (infra_terraform=0, live_deploy=1, cloud=2)
        suffix_parts = parts[3:]  # scope_shared, durable etc
        logical = "-".join(suffix_parts) if suffix_parts else ""
        cloud = path_cloud
    else:
        logical = "-".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "")

    if "scope-shared" in logical or "scope_shared" in logical:
        logical = logical.replace("scope-shared", "shared").replace("scope_shared", "shared")
    return f"{cloud}-{logical}" if logical else cloud

def resolve_region(cli_region: str | None = None) -> str:
    """Region resolution order: --region (CLI), CLOUD_REGION (env). Fails if none set."""
    if cli_region and str(cli_region).strip():
        return str(cli_region).strip()
    region = os.getenv("CLOUD_REGION", "").strip()
    if not region:
        raise EnvVarNotFound(
            "CLOUD_REGION",
            hint="Set CLOUD_REGION in .env or pass --cloud-region (orchestrator) / --region (deploy/teardown).",
        )
    return region

def backend_config(stack_dir: str, env: str, region: str | None = None, cloud: str = "aws") -> list[str]:
    bucket = require("TF_STATE_BUCKET")
    backend_region = region or resolve_region(None)
    prefix = os.getenv("TF_STATE_PREFIX", require("FRU_PREFIX"))
    stack_id = stack_id_from_dir(stack_dir, cloud)
    if region:
        key = f"{prefix}/{env}/{region}/{stack_id}.tfstate"
    else:
        key = f"{prefix}/{env}/{stack_id}.tfstate"
    cfg = [
        f"bucket={bucket}",
        f"key={key}",
        f"region={backend_region}",
        "encrypt=true",
        "use_lockfile=true",
    ]
    table = os.getenv("TF_STATE_LOCK_TABLE") or os.getenv("TF_LOCK_TABLE") or ""
    if table.strip():
        cfg.append(f"dynamodb_table={table.strip()}")
    return cfg
