"""
Environment-specific utilities.
Contains cloud-agnostic interfaces (cloud_shared) and provider implementations:
- cloud_shared: Interfaces (LLMClient, StorageBackend), provider detection, credentials
- aws: Bedrock, S3, RDS Data API
- local: Claude API, local filesystem
- gcp: Placeholder for GCP (Gemini, GCS, Cloud SQL)

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""

