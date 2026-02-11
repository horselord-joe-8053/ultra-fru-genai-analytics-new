"""
Shared heartbeat utilities for long-running operations.
Used by teardown, verify, and any subprocess/polling that needs periodic feedback.
"""
import shlex
import subprocess
import threading
import time
from typing import Optional

from tools import logger
from tools._env import load_dotenv, get_int_env

load_dotenv()

DEFAULT_HEARTBEAT_INTERVAL_SEC = get_int_env("VERIFY_HEARTBEAT_INTERVAL_SEC", 30)


def sleep_with_heartbeat(
    seconds: int,
    message: str,
    interval_sec: Optional[int] = None,
) -> None:
    """Sleep with periodic heartbeat. Long waits (e.g. CloudFront OAC retry) would otherwise appear hung."""
    interval = interval_sec or DEFAULT_HEARTBEAT_INTERVAL_SEC
    start = time.time()
    last_heartbeat = 0
    while (time.time() - start) < seconds:
        elapsed = int(time.time() - start)
        if elapsed - last_heartbeat >= interval and elapsed > 0:
            logger.info(f"[heartbeat] {message} (elapsed: {elapsed}s)")
            last_heartbeat = elapsed
        time.sleep(1)


def run_with_heartbeat(
    cmd: list,
    cwd: str,
    env: dict,
    description: str,
    interval_sec: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """
    Run command with heartbeat. Uses capture_output=True to inspect stderr for retry patterns;
    heartbeat thread provides feedback during long init/destroy runs.
    """
    interval = interval_sec or DEFAULT_HEARTBEAT_INTERVAL_SEC
    logger.info(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    elapsed_ref = [0]
    stop = threading.Event()

    def heartbeat():
        while not stop.is_set():
            if stop.wait(1):
                return
            elapsed_ref[0] += 1
            if elapsed_ref[0] % interval == 0 and elapsed_ref[0] > 0:
                logger.info(f"[heartbeat] {description} (elapsed: {elapsed_ref[0]}s)")

    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    finally:
        stop.set()
        t.join(timeout=2)


def update_heartbeat(
    elapsed: int,
    last_heartbeat: int,
    interval_sec: int,
    message: str,
) -> int:
    """
    For polling loops: if interval has passed since last heartbeat, log message and return elapsed.
    Otherwise return last_heartbeat. Use as: last_heartbeat = update_heartbeat(...).
    """
    if elapsed - last_heartbeat >= interval_sec and elapsed > 0:
        logger.info(message)
        return elapsed
    return last_heartbeat
