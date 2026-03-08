#!/usr/bin/env python3
"""
Start local API and frontend in background. Writes PIDs to .fru_local.pids for shutdown_local.

Usage:
  python tools/local/start_local.py

Called by: orchestrator.py deploy --provider local --start-local
"""
import os
import socket
import subprocess
import sys
import time

import requests

from tools.cloud_shared.analytics_schedule import get_required_analytics_scheduler_interval_seconds
from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEMO_DIR = os.path.join(PROJECT_ROOT, "tools", "local", "memo")
PID_FILE = os.path.join(MEMO_DIR, ".fru_local.pids")
FRONTEND_PORT = 5173


def _port_free(port: int) -> bool:
    """Check if port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_api_port() -> int:
    """Use LOCAL_API_PORT if set and free; else try 5001, 5002, ..."""
    explicit = os.environ.get("LOCAL_API_PORT")
    if explicit:
        try:
            p = int(explicit)
            if _port_free(p):
                return p
            logger.warning(f"Port {p} (LOCAL_API_PORT) in use; trying alternatives")
        except ValueError:
            pass
    for port in range(5001, 5015):
        if _port_free(port):
            return port
    raise RuntimeError("No free port in 5001-5014")


def _wait_for_api(base_url: str, timeout_sec: int = 60) -> bool:
    """Poll /health until API responds or timeout."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = requests.get(f"{base_url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> int:
    logger.step("Starting local API and frontend")
    os.makedirs(MEMO_DIR, exist_ok=True)

    api_port = _find_api_port()
    base_url = os.environ.get("LOCAL_API_URL") or f"http://localhost:{api_port}"

    env = os.environ.copy()
    env["PORT"] = str(api_port)
    env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "core_app")
    # Frontend Vite proxy must target same port
    env["LOCAL_API_PORT"] = str(api_port)
    env["VITE_API_PORT"] = str(api_port)

    # Start API (Flask)
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "backend.api.app"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=open(os.path.join(MEMO_DIR, ".fru_local_api.log"), "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    logger.info(f"API started (PID {api_proc.pid}, port {api_port})")

    # Start frontend (Vite) - inherits LOCAL_API_PORT/VITE_API_PORT for proxy
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(PROJECT_ROOT, "core_app", "frontend"),
        env=env,
        stdout=open(os.path.join(MEMO_DIR, ".fru_local_frontend.log"), "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    logger.info(f"Frontend started (PID {frontend_proc.pid}, port {FRONTEND_PORT})")

    pids_to_write = [api_proc.pid, frontend_proc.pid]
    scheduler_proc = None
    if os.environ.get("ENABLE_ANALYTICS_SCHEDULER", "").lower() in ("true", "1", "yes"):
        scheduler_proc = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "local", "scheduler_local.py")],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=open(os.path.join(MEMO_DIR, ".fru_local_scheduler.log"), "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        if scheduler_proc:
            pids_to_write.append(scheduler_proc.pid)
            interval = get_required_analytics_scheduler_interval_seconds()
            logger.info(f"Analytics scheduler started (PID {scheduler_proc.pid}, interval={interval}s)")

    with open(PID_FILE, "w") as f:
        f.write("\n".join(str(p) for p in pids_to_write) + "\n")
    with open(os.path.join(MEMO_DIR, ".fru_local_api_port"), "w") as f:
        f.write(str(api_port))

    logger.info("Waiting for API to be ready...")
    if not _wait_for_api(base_url):
        logger.error("API did not become ready in time")
        return 1

    logger.success("Local API and frontend started")
    logger.info(f"API: http://localhost:{api_port}  Frontend: http://localhost:{FRONTEND_PORT}")
    logger.info("Shutdown: python orchestrator.py deploy --provider local --shutdown-local (or teardown)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
