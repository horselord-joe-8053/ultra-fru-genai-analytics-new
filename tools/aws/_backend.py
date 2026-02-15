
import os
from tools._env import require

def stack_id_from_dir(stack_dir: str, cloud: str = "aws") -> str:
    """Extract logical stack name from path. Cloud comes from caller (tools/aws vs tools/gcp), not from path.
    Strips first path component (deploy root) without hardcoding names; rest becomes logical id."""
    parts = stack_dir.strip("/").split("/")
    logical = "-".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "")
    return f"{cloud}-{logical}" if logical else cloud

def resolve_region(cli_region: str | None = None) -> str:
    """Region resolution order: --region (CLI), CLOUD_REGION (env), AWS_REGION (env), us-east-1."""
    if cli_region and cli_region.strip():
        return cli_region.strip()
    return (
        os.getenv("CLOUD_REGION", "").strip()
        or os.getenv("AWS_REGION", "").strip()
        or "us-east-1"
    )

def backend_config(stack_dir: str, env: str, region: str | None = None, cloud: str = "aws") -> list[str]:
    bucket = require("TF_STATE_BUCKET")
    backend_region = os.getenv("CLOUD_REGION", "").strip() or require("AWS_REGION")
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
