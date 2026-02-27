"""
Cloud provider detection.
Returns the active cloud provider based on environment variables.
Used by credentials check, storage factory, and health endpoint.

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""
import os


def get_cloud_provider() -> str:
    """
    Detect the active cloud provider from environment variables.

    Detection order:
    1. CLOUD_PROVIDER (explicit override)
    2. GCP_PROJECT_ID or GOOGLE_APPLICATION_CREDENTIALS → gcp
    3. CLOUD_REGION + AWS vars → aws
    4. Default → local

    Returns:
        One of: "aws", "gcp", "local"
    """
    explicit = os.environ.get("CLOUD_PROVIDER", "").strip().lower()
    if explicit in ("aws", "gcp", "local"):
        return explicit

    # GCP: project or credentials set
    if os.environ.get("GCP_PROJECT_ID", "").strip():
        return "gcp"
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip():
        return "gcp"

    # AWS: region + typical AWS env
    cloud_region = os.environ.get("CLOUD_REGION", "").strip()
    if cloud_region and (
        os.environ.get("AWS_ACCESS_KEY_ID") or
        os.environ.get("AWS_PROFILE") or
        os.environ.get("AWS_BEDROCK_MODEL_ID") or
        os.environ.get("AWS_BEDROCK_INFERENCE_PROFILE_ID")
    ):
        return "aws"

    # Default: local
    return "local"
