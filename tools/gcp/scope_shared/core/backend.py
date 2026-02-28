"""
GCP Terraform state backend resolution.
Reference: tools/aws/scope_shared/core/backend.py (resolve_region, state bucket, stack_id, resource names).
GCS bucket for state; no DynamoDB (GCS has built-in locking).
"""
import os
import subprocess

from tools.cloud_shared.env import require, EnvVarNotFound


def stack_id_from_dir(stack_dir: str, cloud: str = "gcp") -> str:
    """Extract logical stack name from path. Same logic as AWS backend.
    Uses canonical IDs (e.g. gcp-shared-durable) when path contains infra_terraform/live_deploy/."""
    path = stack_dir.strip("/").replace("\\", "/")
    parts = path.split("/")

    # Canonical: infra_terraform/live_deploy/gcp/scope_shared/durable -> gcp-shared-durable
    if "infra_terraform/live_deploy/" in path:
        idx = path.index("infra_terraform/live_deploy/") + len("infra_terraform/live_deploy/")
        suffix = path[idx:]
        suffix_parts = suffix.split("/")
        if len(suffix_parts) >= 2:
            path_cloud = suffix_parts[0]
            rest = suffix_parts[1:]
            logical = "-".join(rest).replace("scope_shared", "shared").replace("scope-shared", "shared")
            return f"{path_cloud}-{logical}" if logical else path_cloud

    if path.startswith("infra_terraform/live_deploy/") and len(parts) >= 4:
        path_cloud = parts[2]
        suffix_parts = parts[3:]
        logical = "-".join(suffix_parts) if suffix_parts else ""
        cloud = path_cloud
    else:
        logical = "-".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "")

    if "scope-shared" in logical or "scope_shared" in logical:
        logical = logical.replace("scope-shared", "shared").replace("scope_shared", "shared")
    return f"{cloud}-{logical}" if logical else cloud


def resolve_region(cli_region: str | None = None) -> str:
    """Region: --region (CLI), GCP_REGION, CLOUD_REGION."""
    if cli_region and str(cli_region).strip():
        return str(cli_region).strip()
    region = os.getenv("GCP_REGION", "").strip() or os.getenv("CLOUD_REGION", "").strip()
    if not region:
        raise EnvVarNotFound(
            "GCP_REGION or CLOUD_REGION",
            hint="Set in .env or pass --cloud-region (orchestrator) / --region (deploy/teardown).",
        )
    return region


def resolve_state_bucket(region: str | None = None) -> str:
    """
    Resolve GCS state bucket.
    Uses PROJ_PREFIX + TF_STATE_BUCKET_COMPONENT + env + region + project_id.
    """
    r = region or resolve_region(None)
    env = os.getenv("FRU_ENV", os.getenv("ENVIRONMENT", "dev"))
    proj = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    gcp_proj = os.getenv("GCP_PROJECT_ID", "").strip()
    comp = os.getenv("TF_STATE_BUCKET_COMPONENT", "").strip() or "tf-state"

    if comp and gcp_proj:
        return f"{proj}-{comp}-{env}-{r}-{gcp_proj}"
    prefix_var = os.getenv("TF_STATE_BUCKET_PREFIX", "").strip()
    if prefix_var and gcp_proj:
        return f"{prefix_var}-{env}-{r}-{gcp_proj}"
    bucket = os.getenv("TF_STATE_BUCKET", "").strip()
    if not bucket:
        raise EnvVarNotFound(
            "TF_STATE_BUCKET or TF_STATE_BUCKET_COMPONENT",
            hint="Set TF_STATE_BUCKET_COMPONENT (preferred) or TF_STATE_BUCKET in .env",
        )
    return bucket


def gcs_delta_bucket(env: str, region: str) -> str:
    """GCS delta bucket: {proj}-{component}-{env}-{region}. Override via GCS_DELTA_COMPONENT."""
    proj = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    comp = os.getenv("GCS_DELTA_COMPONENT", "").strip() or "delta-internal"
    return f"{proj}-{comp}-{env}-{region}"


def backend_config(stack_dir: str, env: str, region: str | None = None, cloud: str = "gcp") -> list[str]:
    """Return -backend-config args for GCS backend."""
    deploy_region = region or resolve_region(None)
    bucket = resolve_state_bucket(deploy_region)
    prefix = os.getenv("TF_STATE_PREFIX", "").strip() or os.getenv("PROJ_PREFIX", "fru")
    stack_id = stack_id_from_dir(stack_dir, cloud)
    key = f"{prefix}/{env}/{deploy_region}/{stack_id}.tfstate"
    return [
        f"bucket={bucket}",
        f"prefix={key}",
    ]
