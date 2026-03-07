#!/usr/bin/env python3
"""
Shutdown local API and frontend. Reads PIDs from .fru_local.pids (written by start_local).

Usage:
  python tools/local/shutdown_local.py

Called by: orchestrator.py deploy --provider local --shutdown-local
           orchestrator.py teardown --provider local (runs shutdown first)
"""
import os
import signal
import sys
import time

from tools.cloud_shared.logging import logger

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PID_FILE = os.path.join(PROJECT_ROOT, ".fru_local.pids")


def main() -> int:
    logger.step("Shutting down local API and frontend")

    if not os.path.exists(PID_FILE):
        logger.info("No .fru_local.pids found; nothing to shut down")
        return 0

    pids = []
    with open(PID_FILE) as f:
        for line in f:
            line = line.strip()
            if line and line.isdigit():
                pids.append(int(line))

    try:
        os.remove(PID_FILE)
    except OSError:
        pass

    def _term(pid: int) -> bool:
        try:
            if hasattr(os, "killpg"):
                os.killpg(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
            return True
        except (ProcessLookupError, OSError):
            return False

    def _kill(pid: int) -> None:
        try:
            if hasattr(os, "killpg"):
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    killed = 0
    for pid in pids:
        if _term(pid):
            killed += 1
            logger.info(f"Sent SIGTERM to PID {pid}")
        else:
            logger.info(f"PID {pid} already gone")

    if killed:
        time.sleep(2)
        for pid in pids:
            _kill(pid)

    logger.success("Local shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
