
import json
import os
import subprocess
from tools.cloud_shared.env import require, EnvVarNotFound

_bucket_region_cache: dict[str, str] = {}
_account_id_cache: str | None = None


def get_account_id() -> str:
    """Get current AWS account ID (cached)."""
    global _account_id_cache
    if _account_id_cache:
        return _account_id_cache
    try:
        out = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout:
            data = json.loads(out.stdout)
            _account_id_cache = data.get("Account", "")
            return _account_id_cache
    except Exception:
        pass
    return ""

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

def _region_env_suffix(region: str) -> str:
    """Convert region to env var suffix: us-east-1 -> us_east_1"""
    return region.replace("-", "_") if region else ""


def resolve_state_bucket(region: str | None = None) -> str:
    """
    Resolve S3 state bucket for the given region.
    Uses PROJ_PREFIX + TF_STATE_BUCKET_COMPONENT + env + region + account_id.
    Fallback: TF_STATE_BUCKET_PREFIX (legacy) or TF_STATE_BUCKET / TF_STATE_BUCKET_{region}.
    """
    r = region or resolve_region(None)
    env = os.getenv("FRU_ENV", os.getenv("ENVIRONMENT", "dev"))
    # Preferred: PROJ_PREFIX + TF_STATE_BUCKET_COMPONENT
    proj = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    comp = os.getenv("TF_STATE_BUCKET_COMPONENT", "").strip()
    if comp:
        account_id = get_account_id()
        if not account_id:
            raise EnvVarNotFound(
                "AWS account ID",
                hint="Run 'aws sts get-caller-identity' to verify credentials.",
            )
        return f"{proj}-{comp}-{env}-{r}-{account_id}"
    # Legacy: TF_STATE_BUCKET_PREFIX
    prefix_var = os.getenv("TF_STATE_BUCKET_PREFIX", "").strip()
    if prefix_var:
        account_id = get_account_id()
        if not account_id:
            raise EnvVarNotFound(
                "AWS account ID",
                hint="Run 'aws sts get-caller-identity' to verify credentials.",
            )
        return f"{prefix_var}-{env}-{r}-{account_id}"
    # Legacy: TF_STATE_BUCKET or per-region override
    suffix = _region_env_suffix(r)
    key = f"TF_STATE_BUCKET_{suffix}" if suffix else "TF_STATE_BUCKET"
    bucket = os.getenv(key, "").strip() or os.getenv("TF_STATE_BUCKET", "").strip()
    if not bucket:
        raise EnvVarNotFound(
            "TF_STATE_BUCKET or TF_STATE_BUCKET_PREFIX",
            hint=f"Set TF_STATE_BUCKET_PREFIX (preferred) or TF_STATE_BUCKET in .env",
        )
    return bucket


def resolve_bucket_region(bucket: str) -> str:
    """
    Resolve the AWS region where the S3 bucket lives (dynamic, via API).
    us-east-1 returns empty from get-bucket-location; we treat that as us-east-1.
    """
    if bucket in _bucket_region_cache:
        return _bucket_region_cache[bucket]
    try:
        out = subprocess.run(
            ["aws", "s3api", "get-bucket-location", "--bucket", bucket],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0:
            raise RuntimeError(f"get-bucket-location failed: {out.stderr}")
        data = json.loads(out.stdout) if out.stdout else {}
        data = data or {}
        loc = (data.get("LocationConstraint") or "").strip()
        # null/empty = us-east-1; "EU" = legacy for eu-west-1
        region = loc or "us-east-1"
        if region == "EU":
            region = "eu-west-1"
        _bucket_region_cache[bucket] = region
        return region
    except Exception as e:
        raise RuntimeError(f"Could not resolve bucket region for {bucket}: {e}") from e


def resolve_state_lock_table(region: str | None = None) -> str:
    """
    Resolve DynamoDB lock table for the given region.
    Uses PROJ_PREFIX + TF_LOCK_TABLE_COMPONENT + region when set.
    Fallback: TF_LOCK_TABLE_PREFIX (legacy) or TF_STATE_LOCK_TABLE / TF_LOCK_TABLE.
    """
    r = region or resolve_region(None)
    # Preferred: PROJ_PREFIX + TF_LOCK_TABLE_COMPONENT
    proj = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    comp = os.getenv("TF_LOCK_TABLE_COMPONENT", "").strip()
    if comp:
        return f"{proj}-{comp}-{r}"
    # Legacy: TF_LOCK_TABLE_PREFIX
    lock_prefix = os.getenv("TF_LOCK_TABLE_PREFIX", "").strip()
    if lock_prefix:
        return f"{lock_prefix}-{r}"
    suffix = _region_env_suffix(r)
    for base in ("TF_STATE_LOCK_TABLE", "TF_LOCK_TABLE"):
        key = f"{base}_{suffix}" if suffix else base
        val = os.getenv(key, "").strip()
        if val:
            return val
    return (os.getenv("TF_STATE_LOCK_TABLE") or os.getenv("TF_LOCK_TABLE") or "").strip()


def backend_config(stack_dir: str, env: str, region: str | None = None, cloud: str = "aws") -> list[str]:
    deploy_region = region or resolve_region(None)
    bucket = resolve_state_bucket(deploy_region)
    # Backend region: resolve dynamically from bucket location (avoids 301 when bucket in different region).
    # TF_STATE_BUCKET_REGION overrides when set (e.g. offline, or to skip API call).
    backend_region = os.getenv("TF_STATE_BUCKET_REGION", "").strip() or resolve_bucket_region(bucket)
    prefix = os.getenv("TF_STATE_PREFIX") or os.getenv("PROJ_PREFIX", "").strip() or require("FRU_PREFIX")
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
    table = resolve_state_lock_table(deploy_region)
    if table:
        cfg.append(f"dynamodb_table={table}")
    return cfg
