"""
Deploy frontend to S3 (build + sync). Matches legacy deploy-frontend.sh behavior.
Ensures S3 bucket has index.html and assets so CloudFront can serve the app.

CloudFront invalidation: After S3 sync, invalidate CloudFront cache so edge locations
serve fresh content (fixes stale index.html → MIME type errors, War Story 42).
Parity with legacy: create invalidation + wait for completion (non-blocking on failure).
"""
import json
import os
import random
import subprocess
import time
from tools.common.logging import logger
from tools._env import load_dotenv

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "core-app", "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")

# Wait-for-invalidation constants (legacy parity: cloudfront-invalidation.sh)
CHECK_INTERVAL_SEC = 30
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1
MAX_RETRY_DELAY = 20
DEFAULT_TIMEOUT_MINUTES = 15


def invalidate_cloudfront(distribution_id: str, region: str | None = None) -> tuple[bool, str | None]:
    """
    Create CloudFront invalidation for /* so edge locations serve fresh content after S3 sync.
    Returns (success, invalidation_id). Caller should call wait_for_invalidation if success.
    """
    if not distribution_id or not distribution_id.strip():
        logger.warning("[CloudFront Invalidation] Skipped: distribution_id is empty")
        return False, None

    logger.step("[CloudFront Invalidation] Creating invalidation for distribution")
    logger.info(f"[CloudFront Invalidation]   Distribution ID: {distribution_id}")
    logger.info("[CloudFront Invalidation]   Paths: /*")

    cmd = [
        "aws", "cloudfront", "create-invalidation",
        "--distribution-id", distribution_id.strip(),
        "--paths", "/*",
    ]
    if region:
        cmd.extend(["--region", region])

    try:
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            invalidation_id = ""
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    invalidation_id = data.get("Invalidation", {}).get("Id", "") or ""
                except json.JSONDecodeError:
                    pass
            logger.success(f"[CloudFront Invalidation] Created invalidation: {invalidation_id or '(id in response)'}")
            return True, invalidation_id or None
        else:
            err = (result.stderr or result.stdout or "").strip()[:300]
            logger.warning(f"[CloudFront Invalidation] Failed: {err}")
            return False, None
    except subprocess.TimeoutExpired:
        logger.warning("[CloudFront Invalidation] Timed out; invalidation may still have been created.")
        return False, None
    except Exception as e:
        logger.warning(f"[CloudFront Invalidation] Error: {e}")
        return False, None


def wait_for_invalidation(
    distribution_id: str,
    invalidation_id: str,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    non_blocking: bool = True,
    region: str | None = None,
) -> bool:
    """
    Poll CloudFront until invalidation status is Completed or timeout.
    Parity with legacy wait_for_invalidation (cloudfront-invalidation.sh).
    Returns True if completed, False on failure/timeout (non_blocking: deploy continues).
    """
    if not distribution_id or not invalidation_id:
        logger.warning("[CloudFront Invalidation] wait_for_invalidation: distribution_id and invalidation_id required")
        return False

    logger.info("[CloudFront Invalidation] Waiting for invalidation to complete...")
    logger.info(f"[CloudFront Invalidation]   Distribution ID: {distribution_id}")
    logger.info(f"[CloudFront Invalidation]   Invalidation ID: {invalidation_id}")
    logger.info(f"[CloudFront Invalidation]   Timeout: {timeout_minutes} minutes (checking every {CHECK_INTERVAL_SEC}s)")
    if non_blocking:
        logger.info("[CloudFront Invalidation]   Mode: Non-blocking (deployment will continue if invalidation fails)")

    timeout_seconds = timeout_minutes * 60
    start = time.time()
    consecutive_failures = 0

    while time.time() - start < timeout_seconds:
        cmd = [
            "aws", "cloudfront", "get-invalidation",
            "--distribution-id", distribution_id,
            "--id", invalidation_id,
        ]
        if region:
            cmd.extend(["--region", region])

        status_check_ok = False
        status_result = ""
        err = ""
        for retry in range(MAX_RETRIES):
            try:
                result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
                err = result.stderr or ""
                if result.returncode == 0:
                    status_check_ok = True
                    status_result = result.stdout or ""
                    consecutive_failures = 0
                    break
            except Exception as e:
                err = str(e)
            if "NoSuchInvalidation" in err:
                logger.warning("[CloudFront Invalidation] NoSuchInvalidation - invalidation may have expired or been pruned.")
                logger.info("[CloudFront Invalidation] You can recreate manually: aws cloudfront create-invalidation --distribution-id ... --paths '/*'")
                return False
            if retry < MAX_RETRIES - 1:
                delay = min(BASE_RETRY_DELAY * (2**retry) + random.randint(0, 1), MAX_RETRY_DELAY)
                logger.warning(f"[CloudFront Invalidation] Status check failed (attempt {retry+1}/{MAX_RETRIES}), retrying in {delay}s...")
                time.sleep(delay)

        if not status_check_ok:
            consecutive_failures += 1
            if consecutive_failures >= MAX_RETRIES:
                logger.warning("[CloudFront Invalidation] Too many consecutive failures; deployment will continue.")
                return False
            time.sleep(CHECK_INTERVAL_SEC)
            continue

        try:
            data = json.loads(status_result)
            status = (data.get("Invalidation") or {}).get("Status", "")
        except json.JSONDecodeError:
            status = ""

        if status == "Completed":
            elapsed = int(time.time() - start)
            logger.success(f"[CloudFront Invalidation] Completed successfully (took {elapsed // 60}m {elapsed % 60}s)")
            return True
        if status == "InProgress":
            elapsed = int(time.time() - start)
            logger.info(f"[CloudFront Invalidation] In progress... ({elapsed // 60}m {elapsed % 60}s elapsed)")
        elif status:
            logger.warning(f"[CloudFront Invalidation] Unexpected status: {status}")
            return False

        time.sleep(CHECK_INTERVAL_SEC)

    logger.warning("[CloudFront Invalidation] Timeout - invalidation still in progress; deployment will continue.")
    logger.info("[CloudFront Invalidation] Fresh content will be available once invalidation completes.")
    return False


def deploy_frontend_to_s3(bucket: str, env: str) -> None:
    """Build frontend and sync to S3. Idempotent. Caller must provide bucket from Terraform output."""
    logger.step("Deploying frontend to S3...")
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
    env_vars.setdefault("VITE_PROVIDER", "aws")
    env_vars.setdefault("VITE_CONTAINER_TYPE", "ecs")
    env_vars.setdefault("VITE_ENVIRONMENT", env)
    subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        env=env_vars,
        check=True,
    )
    logger.success("Frontend built")

    s3_uri = f"s3://{bucket}"
    logger.info(f"Syncing {DIST_DIR} -> {s3_uri}")
    subprocess.run(
        ["aws", "s3", "sync", DIST_DIR, s3_uri, "--delete"],
        cwd=REPO_ROOT,
        check=True,
    )
    logger.success(f"Frontend deployed to {s3_uri}")
