"""
Set up the GCS remote state backend for Terraform/OpenTofu.

Creates the GCS state bucket if missing (versioning enabled).
Uses google-cloud-storage Python client (no gsutil required).
Reference: tools/aws/scope_shared/deploy/setup_state_backend.py (AWS S3 equivalent).

WHY OUTSIDE TERRAFORM: Chicken-and-egg—Terraform needs a backend before `tofu init`, so this
bucket must exist first. Created via GCS client before any Terraform runs. Never destroyed by
teardown (even --incl-dura-all); manual deletion only when decommissioning.

Bucket: {prefix}-tf-state-{env}-{region}-{project_id}
State paths: {prefix}/{env}/{region}/{stack_id}.tfstate
"""
import os
import json
from pathlib import Path

from tools.gcp.scope_shared.core.backend import resolve_region, resolve_state_bucket

def _is_valid_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def _load_multiline_json_from_env(env_path: Path, key: str) -> str | None:
    """Extract multi-line JSON value for key from .env (dotenv often fails on multi-line)."""
    text = env_path.read_text()
    prefix = f"{key}="
    if prefix not in text:
        return None
    start = text.index(prefix) + len(prefix)
    rest = text[start:].lstrip()
    if not rest.startswith("{"):
        return None
    depth = 0
    end = 0
    for i, c in enumerate(rest):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == 0:
        return None
    return rest[:end]


def _load_env():
    env_path = Path(".env")
    if not env_path.exists() and Path("env.fru").exists():
        env_path = Path("env.fru")
    if not env_path.exists():
        return
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from dotenv import load_dotenv as dotenv_load
            dotenv_load(env_path, override=True)
    except ImportError:
        from tools.cloud_shared.env import load_dotenv
        load_dotenv()
    # Fix GOOGLE_APPLICATION_CREDENTIALS_JSON when dotenv truncated multi-line (common with .env)
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    needs_fix = (
        raw
        and raw.startswith("{")
        and (not raw.rstrip().endswith("}") or not _is_valid_json(raw))
    )
    if needs_fix or (raw and not _is_valid_json(raw)):
        fixed = _load_multiline_json_from_env(env_path, "GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if fixed:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"] = fixed


def load_gcp_env():
    """Load .env with multi-line JSON support. Call from verify/scripts that need GCP credentials."""
    _load_env()


_load_env()


def _get_storage_client():
    """Get GCS client. Uses GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_APPLICATION_CREDENTIALS_JSON, or ADC."""
    from google.cloud import storage
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds_path and os.path.isfile(creds_path):
        return storage.Client.from_service_account_json(creds_path)
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    if creds_json:
        try:
            info = json.loads(creds_json)
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(info)
            return storage.Client(credentials=creds, project=info.get("project_id"))
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS_JSON invalid: {e}. "
                "Use GOOGLE_APPLICATION_CREDENTIALS with a file path, or fix the JSON."
            ) from e
    return storage.Client()


def exists_gcs(bucket: str) -> bool:
    try:
        client = _get_storage_client()
        client.get_bucket(bucket)
        return True
    except Exception as e:
        # 404 = bucket doesn't exist
        if "404" in str(e) or "Not Found" in str(e) or "not find" in str(e).lower():
            return False
        # Credentials error - re-raise with hint
        if "DefaultCredentialsError" in type(e).__name__ or "credentials" in str(e).lower():
            raise RuntimeError(
                f"GCP credentials not found: {e}. "
                "Set GOOGLE_APPLICATION_CREDENTIALS (file path) or GOOGLE_APPLICATION_CREDENTIALS_JSON (inline JSON)."
            ) from e
        return False


def create_gcs(bucket: str, region: str):
    client = _get_storage_client()
    from google.cloud import storage
    b = client.create_bucket(bucket, location=region)
    b.versioning_enabled = True
    b.patch()


def main():
    region = resolve_region(None)
    bucket = resolve_state_bucket(region)

    if not exists_gcs(bucket):
        print("Creating state bucket:", bucket, "in", region)
        create_gcs(bucket, region)
    else:
        print("State bucket exists:", bucket)


if __name__ == "__main__":
    main()
