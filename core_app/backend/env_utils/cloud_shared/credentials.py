"""
Provider-agnostic credentials status check.
Used by /health endpoint to report credential configuration without direct boto3 in app.py.
Boto3 and other cloud SDK imports are confined to this module.

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""
from backend.env_utils.cloud_shared.provider import get_cloud_provider


def check_credentials_status() -> dict:
    """
    Check credentials status for the active cloud provider.
    Returns a dict suitable for merging into /health response.

    Returns:
        Dict with provider key and status, e.g.:
        - {"aws": "configured"} or {"aws": "not_configured"}
        - {"gcp": "configured"} or {"gcp": "not_configured"}
        - {"local": "ok"}
    """
    provider = get_cloud_provider()

    if provider == "aws":
        try:
            import boto3
            creds = boto3.Session().get_credentials()
            return {"aws": "configured" if creds else "not_configured"}
        except Exception:
            return {"aws": "not_configured"}

    if provider == "gcp":
        import os
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
        if creds_path or creds_json:
            return {"gcp": "configured"}
        return {"gcp": "not_configured"}

    # local
    return {"local": "ok"}
