#!/usr/bin/env python3
"""
Diagnostic script for get_image_tags. Run locally with GCP auth to debug why 'latest' is missing.

Usage:
  python tools/standalone/diagnose_image_tags.py
  # Uses CONTAINER_IMAGE from env or a default GCP dev image.

Set CONTAINER_IMAGE, CLOUD_PROVIDER, CLOUD_REGION if needed.
"""
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Enable INFO logging for image_registry_tags
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("tools.cloud_shared.image_registry_tags").setLevel(logging.DEBUG)

def main():
    container_image = os.environ.get(
        "CONTAINER_IMAGE",
        "us-central1-docker.pkg.dev/fru-proj-1/fru-api-img-gcp-dev/app:fru_dev_20260317_0112676_dirty_20260317_235345_p1100",
    )
    provider = os.environ.get("CLOUD_PROVIDER", "gcp")
    region = os.environ.get("CLOUD_REGION", "us-central1")

    print(f"Diagnosing get_image_tags:")
    print(f"  container_image: {container_image}")
    print(f"  provider: {provider}")
    print(f"  region: {region}")
    print()

    from tools.cloud_shared.image_registry_tags import get_image_tags

    tags = get_image_tags(container_image, provider, region)
    print(f"\nResult: {tags}")
    return 0 if tags else 1

if __name__ == "__main__":
    sys.exit(main())
