"""
Deploy frontend to S3 (build + sync). Matches legacy deploy-frontend.sh behavior.
Ensures S3 bucket has index.html and assets so CloudFront can serve the app.
"""
import os
import subprocess
from tools import logger
from tools._env import load_dotenv

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "core-app", "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")


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
