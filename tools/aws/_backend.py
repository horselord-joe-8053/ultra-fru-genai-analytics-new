
import os
from tools._env import require

def stack_id_from_dir(stack_dir: str) -> str:
    s = stack_dir.strip("/")
    # live-deploy-* first to avoid partial replacement
    s = s.replace("live-deploy-aws/", "aws-").replace("live-deploy-gcp/", "gcp-")
    s = s.replace("deploy-aws/", "aws-").replace("deploy-gcp/", "gcp-")
    s = s.replace("/", "-")
    return s

def backend_config(stack_dir: str, env: str) -> list[str]:
    bucket = require("TF_STATE_BUCKET")
    region = require("AWS_REGION")
    prefix = os.getenv("TF_STATE_PREFIX", require("FRU_PREFIX"))
    key = f"{prefix}/{env}/{stack_id_from_dir(stack_dir)}.tfstate"
    cfg = [
        f"bucket={bucket}",
        f"key={key}",
        f"region={region}",
        "encrypt=true",
        "use_lockfile=true",
    ]
    # Optional DynamoDB lock table (not required when use_lockfile=true)
    table = os.getenv("TF_STATE_LOCK_TABLE") or os.getenv("TF_LOCK_TABLE") or ""
    if table.strip():
        cfg.append(f"dynamodb_table={table.strip()}")
    return cfg
