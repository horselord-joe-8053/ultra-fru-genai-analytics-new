
import os
import sys
import time
import threading
import datetime
from typing import Optional

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def _log_prefix(level: str) -> str:
    """Format: [YYYY-MM-DD HH:MM:SS.mmm TZ] [LEVEL] message (aligned with legacy lib/logger.sh)"""
    now = datetime.datetime.now()
    ms = int(now.microsecond / 1000)
    ts = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{ms:03d}"
    tz = time.tzname[0] if time.tzname else "UTC"

    color = NC
    if level == "INFO":
        color = BLUE
    elif level == "SUCCESS":
        color = GREEN
    elif level == "WARNING":
        color = YELLOW
    elif level == "ERROR":
        color = RED

    return f"[{ts} {tz}] {color}[{level}]{NC} "

def info(msg: str):
    print(f"{_log_prefix('INFO')}{msg}", flush=True)

def success(msg: str):
    print(f"{_log_prefix('SUCCESS')}{msg}", flush=True)

def warning(msg: str):
    print(f"{_log_prefix('WARNING')}{msg}", flush=True)

def error(msg: str):
    print(f"{_log_prefix('ERROR')}{msg}", file=sys.stderr, flush=True)

def step(msg: str):
    print(f"\n{_log_prefix('SUCCESS')}{GREEN}==>{NC} {BLUE}{msg}{NC}", flush=True)


def phase_start(phase_num: int, total: int, name: str):
    """Emit phase start marker. Use for deploy/teardown/verify stage boundaries."""
    print(f"\n{_log_prefix('INFO')}{BLUE}═══ [{phase_num}/{total}] {name} ── START{NC}", flush=True)


def phase_end(phase_num: int, total: int, name: str, duration_sec: int):
    """Emit phase end marker. Use for deploy/teardown/verify stage boundaries."""
    dur = f"{duration_sec}s" if duration_sec < 60 else f"{duration_sec // 60}m{duration_sec % 60}s"
    print(f"{_log_prefix('SUCCESS')}{GREEN}═══ [{phase_num}/{total}] {name} ── DONE ({dur}){NC}", flush=True)


def operation_start(operation: str, scope: str, env: str, region: str):
    """Emit operation start marker (deploy/teardown/verify)."""
    print(f"\n{_log_prefix('SUCCESS')}{GREEN}═══ {operation} START: scope={scope} env={env} region={region} ═══{NC}", flush=True)


def operation_end(operation: str, scope: str, env: str, region: str, duration_sec: int, ok: bool = True):
    """Emit operation end marker (deploy/teardown/verify)."""
    dur = f"{duration_sec}s" if duration_sec < 60 else f"{duration_sec // 60}m{duration_sec % 60}s"
    status = "DONE" if ok else "FAILED"
    prefix = _log_prefix("SUCCESS" if ok else "ERROR")
    color = GREEN if ok else RED
    print(f"\n{prefix}{color}═══ {operation} {status}: scope={scope} env={env} region={region} ({dur}) ═══{NC}", flush=True)

class Heartbeat:
    """
    Context manager for background heartbeats.
    Usage:
        with Heartbeat("Processing data...", interval=10):
            long_running_task()
    """
    def __init__(self, message: str, interval: Optional[int] = None, timeout: Optional[int] = None):
        from tools.cloud_shared.env import load_dotenv, get_int_env
        load_dotenv()
        
        self.message = message
        self.interval = interval or get_int_env("LOGGING_TASK_HEARBEAT_INTERVAL", 10)
        self.timeout = timeout or get_int_env("LOGGING_TASK_DEFAULT_TIMEOUT", 300)
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[float] = None

    def _run(self):
        # Local refs to avoid None issues with type checker
        start_time = self._start_time
        if start_time is None:
            return
            
        counter = 0
        while not self._stop_event.is_set():
            time.sleep(self.interval)
            if self._stop_event.is_set():
                break
            
            counter += 1
            elapsed = int(time.time() - start_time)
            if self.timeout > 0 and elapsed > self.timeout:
                error(f"Heartbeat timeout: '{self.message}' exceeded {self.timeout}s")
                # We don't raise here as it's in a thread, but the user will see it
                break

            info(f"[HEARTBEAT] {self.message} ... ({elapsed}s elapsed)")

    def __enter__(self):
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            # We don't join for long as it's a daemon and might be sleeping
            thread.join(timeout=0.1)
        
        start_time = self._start_time
        if start_time is not None:
            elapsed = int(time.time() - start_time)
            if exc_type:
                error(f"Task failed: '{self.message}' (after {elapsed}s)")
            else:
                success(f"Task completed: '{self.message}' (took {elapsed}s)")
