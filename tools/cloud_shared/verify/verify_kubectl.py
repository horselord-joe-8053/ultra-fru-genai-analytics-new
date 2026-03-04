"""
Shared kubectl verification helpers.

Used by AWS and GCP verify_all_teardown to check namespace is gone.
"""
import subprocess

from tools.cloud_shared.logging import logger


def verify_kubectl_namespace_gone(namespace: str) -> bool:
    """
    Verify Kubernetes namespace is gone. Returns True if ok (namespace not found).
    kubectl get ns X raises CalledProcessError when namespace does not exist.
    """
    logger.info(f"Verifying Kubernetes namespace '{namespace}' is gone...")
    try:
        subprocess.check_call(
            ["kubectl", "get", "ns", namespace],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.error(f"✗ Namespace '{namespace}' still exists!")
        return False
    except subprocess.CalledProcessError:
        logger.success(f"✓ Namespace '{namespace}' is gone.")
        return True
