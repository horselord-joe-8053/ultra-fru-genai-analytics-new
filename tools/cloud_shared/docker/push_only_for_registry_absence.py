"""
Push local images to the remote registry only when the registry does not already have them.

Used after build was skipped (content-hash match or --skip-build): if the target registry
is empty (e.g. first deploy to a new region), tag and push local canonical images so
deploy does not fail with ImageNotFoundException / missing image.

- AWS: call from deploy when content-skip or --skip-build; uses ECR and build_and_push_images --push-only.
- GCP: call from deploy when content-skip or --skip-build; uses Artifact Registry and build script --push-only.
- Local: do not call (no remote registry; images are local only).
"""
from typing import Callable

from tools.cloud_shared.logging import logger


def push_only_for_registry_absence(
    registry_has_images: Callable[[], bool],
    push_local_images: Callable[[], None],
    *,
    log_prefix: str = "[PUSH-ONLY]",
) -> None:
    """
    If the target registry already has the required images, return. Otherwise run
    push_local_images() to tag and push local canonical images into the registry.

    Call this only when build was skipped (content-hash match or --skip-build).
    Local provider does not call this (no remote registry).
    """
    if registry_has_images():
        return
    logger.info(f"{log_prefix} Target registry empty; pushing from local canonical images")
    try:
        push_local_images()
    except Exception as e:
        logger.warning(f"{log_prefix} Push failed (no local images?): {e}")
