"""
Deploy frontend to GCS (build + sync). GCP equivalent of AWS deploy_frontend.

Builds Vite app and syncs to GCS bucket. Optionally invalidates Cloud CDN cache.
Reference: tools/aws/scope_shared/deploy/deploy_frontend.py
"""
import os
import subprocess

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "core_app", "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")


def deploy_frontend_to_gcs(
    bucket: str,
    env: str,
    scope: str = "nonkube",
    project_id: str | None = None,
) -> None:
    """Build frontend and sync to GCS. Idempotent."""
    logger.step("Deploying frontend to GCS...")
    if not os.path.isdir(FRONTEND_DIR):
        logger.warning(f"Frontend dir not found: {FRONTEND_DIR}; skipping frontend deploy")
        return

    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        logger.info("Installing frontend dependencies (npm install)...")
        subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)
        logger.success("Dependencies installed")

    logger.info("Building frontend...")
    env_vars = os.environ.copy()
    env_vars.setdefault("VITE_PROVIDER", "gcp")
    env_vars.setdefault("VITE_SCOPE", scope)
    env_vars.setdefault("VITE_ENVIRONMENT", env)
    subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        env=env_vars,
        check=True,
    )
    logger.success("Frontend built")

    gs_uri = f"gs://{bucket}"
    logger.info(f"Syncing {DIST_DIR} -> {gs_uri}")
    # gsutil rsync does not support -p; uses gcloud default project
    cmd = ["gsutil", "-m", "rsync", "-r", "-d", DIST_DIR, gs_uri]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    logger.success(f"Frontend deployed to {gs_uri}")


def invalidate_cloud_cdn(url_map_name: str, project_id: str) -> bool:
    """
    Invalidate Cloud CDN cache for URL map so edge locations serve fresh content.
    Returns True if invalidation was triggered.
    """
    if not url_map_name or not url_map_name.strip():
        logger.warning("[Cloud CDN Invalidation] Skipped: url_map_name is empty")
        return False

    logger.step("[Cloud CDN Invalidation] Invalidating cache...")
    logger.info(f"[Cloud CDN Invalidation]   URL map: {url_map_name}")
    logger.info("[Cloud CDN Invalidation]   Paths: /*")

    try:
        subprocess.run(
            [
                "gcloud", "compute", "url-maps", "invalidate-cdn-cache", url_map_name,
                "--path", "/*",
                "--project", project_id,
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        logger.success("[Cloud CDN Invalidation] Cache invalidation triggered")
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()[:300]
        logger.warning(f"[Cloud CDN Invalidation] Failed: {err}")
        return False
    except Exception as e:
        logger.warning(f"[Cloud CDN Invalidation] Error: {e}")
        return False
