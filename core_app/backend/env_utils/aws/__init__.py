"""
AWS cloud environment utilities.
Contains implementations for AWS services:
- bedrock_client: LLM via Bedrock
- s3_helpers: S3 file operations
- storage_backend: S3StorageBackend for filesystem factory
- rds_data_api: RDS Data API for ETL

Applicable environment: [aws {ecs | eks}]
"""

