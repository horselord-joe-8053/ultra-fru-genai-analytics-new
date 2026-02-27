"""
Cloud-agnostic interfaces and utilities.
Contains abstract interfaces (LLMClient, StorageBackend) and provider detection.
No cloud-specific imports; implementations live in aws/, local/, gcp/.

Applicable environment: [local] [aws {ecs | eks}] [gcp {cloud-run | gke}]
"""
