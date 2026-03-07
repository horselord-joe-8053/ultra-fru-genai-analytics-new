#!/usr/bin/env python3
"""
Start local API and frontend in background. Writes PIDs to .fru_local.pids for shutdown_local.

Usage:
  python tools/local/start_local.py

Called by: orchestrator.py deploy --provider local --start-local
"""
import os
import subprocess
import sys
import time

import requests

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PID_FILE = os.path.join(PROJECT_ROOT, ".fru_local.pids")
API_PORT = int(os.environ.get("LOCAL_API_PORT", "5001"))
FRONTEND_PORT = 5173
BASE_URL = os.environ.get("LOCAL_API_URL", f"http://localhost:{API_PORT}")


def _wait_for_api(timeout_sec: int = 60) -> bool:
    """Poll /health until API responds or timeout."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> int:
    logger.step("Starting local API and frontend")

    env = os.environ.copy()
    env["PORT"] = str(API_PORT)
    env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "core_app")

    # Start API (Flask)
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "backend.api.app"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=open(os.path.join(PROJECT_ROOT, ".fru_local_api.log"), "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    logger.info(f"API started (PID {api_proc.pid}, port {API_PORT})")

    # Start frontend (Vite)
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(PROJECT_ROOT, "core_app", "frontend"),
        stdout=open(os.path.join(PROJECT_ROOT, ".fru_local_frontend.log"), "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    logger.info(f"Frontend started (PID {frontend_proc.pid}, port {FRONTEND_PORT})")

    with open(PID_FILE, "w") as f:
        f.write(f"{api_proc.pid}\n{frontend_proc.pid}\n")

    logger.info("Waiting for API to be ready...")
    if not _wait_for_api():
        logger.error("API did not become ready in time")
        return 1

    logger.success("Local API and frontend started")
    logger.info(f"API: http://localhost:{API_PORT}  Frontend: http://localhost:{FRONTEND_PORT}")
    logger.info("Shutdown: python orchestrator.py deploy --provider local --shutdown-local (or teardown)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
