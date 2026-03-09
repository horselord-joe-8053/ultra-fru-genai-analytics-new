#!/usr/bin/env python3
"""
Start local API and frontend in background. Writes PIDs to .fru_local.pids for shutdown_local.

Usage:
  python tools/local/start_local.py

Called by: orchestrator.py deploy --provider local --start-local
"""
import argparse
import os
import socket
import subprocess
import sys
import time

import requests

from tools.cloud_shared.analytics_schedule import get_required_analytics_scheduler_interval_seconds
from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.local.scope_shared.local_deploy_config import get_memo_dir, get_ports_for_scope

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEMO_DIR = get_memo_dir()
PID_FILE = os.path.join(MEMO_DIR, ".fru_local.pids")


def _port_free(port: int) -> bool:
    """Check if port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="all")
    ap.add_argument("--skip-api", action="store_true", help="API in container/k8s; start frontend only")
    ap.add_argument("--api-port", type=int, help="API port for frontend proxy (default: 5001 nonkube, 30080 kube)")
    args = ap.parse_args()

    # For local deploys, API is expected to be running in Docker/k8s already.
    # start_local.py is responsible for starting the frontend(s) and (for nonkube)
    # the scheduler. We intentionally fail-fast if an unexpected scope is used.
    if args.scope == "all":
        scopes = ["nonkube", "kube"]
    else:
        scopes = [args.scope]

    if args.api_port and len(scopes) > 1:
        logger.warning("--api-port is ignored when scope=all (multiple scopes).")

    logger.step(f"Starting local frontend(s) for scope(s): {', '.join(scopes)}")
    os.makedirs(MEMO_DIR, exist_ok=True)
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "core_app")

    pids_to_write = []
    api_port = None
    frontend_port = None

    for scope in scopes:
        # Fail-fast: scope must be one of the explicit values we understand.
        if scope not in ("kube", "nonkube"):
            raise ValueError(
                f"Scope '{scope}' invalid for start_local; use 'kube', 'nonkube', or 'all'"
            )

        ports = get_ports_for_scope(scope)
        scope_api_port = ports["api_port"]
        scope_frontend_port = ports["frontend_port"]

        # Optional per-scope overrides for API port exposed to the frontend.
        # VITE_* vars are special: they are injected into the browser bundle
        # (import.meta.env). start_local.py is the single place that sets them.
        override_key = "VITE_API_PORT_KUBE" if scope == "kube" else "VITE_API_PORT_NONKUBE"
        override = os.environ.get(override_key)

        env = base_env.copy()
        env["VITE_API_PORT"] = override or str(scope_api_port)

        logger.info(
            f"[LOCAL] Scope={scope}: api_port={scope_api_port}, "
            f"frontend_port={scope_frontend_port}, VITE_API_PORT={env['VITE_API_PORT']}"
        )

        # Start frontend (Vite) - port from config; proxy target from VITE_API_PORT
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(scope_frontend_port)],
            cwd=os.path.join(PROJECT_ROOT, "core_app", "frontend"),
            env=env,
            stdout=open(os.path.join(MEMO_DIR, f".fru_local_frontend_{scope}.log"), "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        logger.info(
            f"Frontend started (scope={scope}, PID {frontend_proc.pid}, port {scope_frontend_port})"
        )
        pids_to_write.append(frontend_proc.pid)

        # Scheduler only for nonkube (kube has CronJob)
        if scope == "nonkube" and os.environ.get("ENABLE_ANALYTICS_SCHEDULER", "").lower() in ("true", "1", "yes"):
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

        # For memo/logging we keep track of the last scope's ports; for scope=all this
        # will be kube, which is fine for informational logging.
        api_port = scope_api_port
        frontend_port = scope_frontend_port

    with open(PID_FILE, "w") as f:
        f.write("\n".join(str(p) for p in pids_to_write) + "\n")
    with open(os.path.join(MEMO_DIR, ".fru_local_api_port"), "w") as f:
        f.write(str(api_port))
    with open(os.path.join(MEMO_DIR, ".fru_local_frontend_port"), "w") as f:
        f.write(str(frontend_port))
    with open(os.path.join(MEMO_DIR, ".fru_local_scope"), "w") as f:
        f.write(args.scope)

    # For local orchestrator flows we assume API is already running (container/k8s).
    # We still probe /health on the chosen api_port so failures show up early.
    base_url = os.environ.get("LOCAL_API_URL") or f"http://localhost:{api_port}"
    logger.info(f"Waiting for API to be ready at {base_url}...")
    if not _wait_for_api(base_url):
        logger.error("API did not become ready in time")
        return 1

    logger.success("Local API and frontend started")
    logger.info(
        f"API: http://localhost:{api_port}  Frontend: http://localhost:{frontend_port} (scope={args.scope})"
    )
    logger.info("Shutdown: python orchestrator.py deploy --provider local --shutdown-local (or teardown)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
