"""
AWS cloud environment utilities.
Contains implementations for AWS services:
- bedrock_client: LLM via Bedrock
- s3_helpers: S3 file operations
- storage_backend: S3StorageBackend for filesystem factory
- rds_data_api: RDS Data API for ETL

Applicable environment: [aws {ecs | eks}]
"""
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.env_utils.cloud_shared.interfaces.llm_client import LLMClient


def get_llm_client() -> Optional["LLMClient"]:
    """Return AWSBedrockClient if Bedrock config present, else None."""
    aws_region = os.environ.get("CLOUD_REGION", "").strip()
    bedrock_profile_id = os.environ.get("AWS_BEDROCK_INFERENCE_PROFILE_ID", "").strip()
    bedrock_model_id = os.environ.get("AWS_BEDROCK_MODEL_ID", "").strip()
    if not aws_region or not (bedrock_profile_id or bedrock_model_id):
        return None
    try:
        from backend.env_utils.aws.bedrock_client import AWSBedrockClient
        return AWSBedrockClient()
    except Exception:
        return None

