#!/usr/bin/env python3
"""
Shutdown local API and frontend.

Default: kill **all** relevant local processes (Vite dev servers and host
backend.api.app instances) associated with this repo, plus any PIDs recorded in
.fru_local.pids. This is defensive so that port assignments from
config/local/local_deploy_config.yaml remain stable and we don't keep orphaned
dev servers around.

Use --kill-last-only to limit shutdown to the last stack started via
start_local.py (PIDs from .fru_local.pids), matching the original behavior.

Usage:
  python tools/local/shutdown_local.py

Called by: orchestrator.py deploy --provider local --shutdown-local
           orchestrator.py teardown --provider local (runs shutdown first)
"""
import os
import signal
import sys
import time
import subprocess

from tools.cloud_shared.logging import logger

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEMO_DIR = os.path.join(PROJECT_ROOT, "tools", "local", "memo")
PID_FILE = os.path.join(MEMO_DIR, ".fru_local.pids")


def _collect_pids_from_file() -> list[int]:
    """Read last-started PIDs from .fru_local.pids (may be empty)."""
    if not os.path.exists(PID_FILE):
        return []
    pids: list[int] = []
    with open(PID_FILE) as f:
        for line in f:
            line = line.strip()
            if line and line.isdigit():
                pids.append(int(line))
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
    return pids

def _collect_extra_pids() -> list[int]:
    """
    Find additional Vite/backend dev processes for this repo.

    We match:
      - node .../core_app/frontend/node_modules/.bin/vite
      - python -m backend.api.app
    with PROJECT_ROOT in the ps line, so we don't touch unrelated projects.
    """
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        return []
    extra: list[int] = []
    for line in out.splitlines()[1:]:
        if PROJECT_ROOT not in line:
            continue
        if "core_app/frontend/node_modules/.bin/vite" not in line and " -m backend.api.app" not in line:
            continue
        parts = line.split()
        if len(parts) > 1 and parts[1].isdigit():
            extra.append(int(parts[1]))
    return extra


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--kill-last-only",
        action="store_true",
        help="Only kill processes recorded in .fru_local.pids (legacy behavior)",
    )
    args = ap.parse_args()

    logger.step("Shutting down local API and frontend")

    pids = _collect_pids_from_file()
    if not args.kill_last_only:
        extra = _collect_extra_pids()
        # Merge and dedupe
        pids = sorted(set(pids + extra))

    def _term(pid: int) -> bool:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except (ProcessLookupError, OSError):
            return False

    def _kill(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    if not pids:
        logger.info("No matching local frontend/backend processes found; nothing to shut down")
        return 0

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
