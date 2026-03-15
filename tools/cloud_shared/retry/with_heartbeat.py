"""
Shared heartbeat utilities for long-running operations.
Used by teardown, verify, and any subprocess/polling that needs periodic feedback.
"""
import shlex
import subprocess
import threading
import time
from typing import Callable, Optional

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, get_int_env

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


def run_with_heartbeat_stream(
    cmd: list,
    cwd: str,
    env: dict,
    description: str,
    interval_sec: Optional[int] = None,
    timeout_sec: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """
    Run command with heartbeat while streaming stdout/stderr. Use for long-running
    subprocesses (e.g. docker build) where we want both child output and periodic
    heartbeat so the process doesn't appear stuck.

    If timeout_sec is set, the process is killed after that many seconds and
    subprocess.TimeoutExpired is raised.
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
                msg = f"[heartbeat] {description} (elapsed: {elapsed_ref[0]}s)"
                if timeout_sec:
                    msg += f" [timeout: {timeout_sec}s]"
                logger.info(msg)

    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, text=True, timeout=timeout_sec)
    finally:
        stop.set()
        t.join(timeout=2)


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


def run_with_heartbeat_stream_capture(
    cmd: list,
    cwd: str,
    env: dict,
    description: str,
    interval_sec: Optional[int] = None,
    timeout_sec: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """
    Run command with heartbeat while streaming stdout/stderr. Also captures output for retry
    pattern matching. Use for tofu destroy so user sees per-resource progress (e.g.
    "module.frontend.aws_s3_bucket.frontend: Destroying...") while still supporting retry.

    If timeout_sec is set, the process is killed after that many seconds. On timeout,
    returns CompletedProcess with returncode=-9 (SIGKILL) and stderr includes timeout message.
    """
    import sys

    interval = interval_sec or DEFAULT_HEARTBEAT_INTERVAL_SEC
    effective_timeout = timeout_sec if timeout_sec and timeout_sec > 0 else None
    logger.info(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    if effective_timeout:
        logger.info(f"[run] timeout={effective_timeout}s (TEARDOWN_DESTROY_TIMEOUT_SEC)")
    elapsed_ref = [0]
    stop = threading.Event()
    captured_out: list[str] = []
    captured_err: list[str] = []

    def heartbeat():
        while not stop.is_set():
            if stop.wait(1):
                return
            elapsed_ref[0] += 1
            if elapsed_ref[0] % interval == 0 and elapsed_ref[0] > 0:
                msg = f"[heartbeat] {description} (elapsed: {elapsed_ref[0]}s)"
                if effective_timeout:
                    msg += f" [timeout: {effective_timeout}s]"
                logger.info(msg)

    def read_stream(pipe, lines: list, stream):
        for line in iter(pipe.readline, ""):
            lines.append(line)
            print(line, end="", file=stream)

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    t_heartbeat = threading.Thread(target=heartbeat, daemon=True)
    t_heartbeat.start()
    t_stdout = threading.Thread(
        target=read_stream, args=(proc.stdout, captured_out, sys.stdout), daemon=True
    )
    t_stderr = threading.Thread(
        target=read_stream, args=(proc.stderr, captured_err, sys.stderr), daemon=True
    )
    t_stdout.start()
    t_stderr.start()
    try:
        proc.wait(timeout=effective_timeout)
    except subprocess.TimeoutExpired:
        logger.error(
            f"Process timed out after {effective_timeout}s. Killing tofu destroy. "
            f"Set TEARDOWN_DESTROY_TIMEOUT_SEC=0 to disable (or increase for longer runs)."
        )
        proc.kill()
        proc.wait(timeout=10)
        out_text = "".join(captured_out)
        err_text = "".join(captured_err)
        err_text += f"\n[TEARDOWN] Process killed after {effective_timeout}s (TEARDOWN_DESTROY_TIMEOUT_SEC)."
        stop.set()
        t_heartbeat.join(timeout=2)
        t_stdout.join(timeout=1)
        t_stderr.join(timeout=1)
        return subprocess.CompletedProcess(proc.args, -9, stdout=out_text, stderr=err_text)
    finally:
        stop.set()
        t_heartbeat.join(timeout=2)
        t_stdout.join(timeout=1)
        t_stderr.join(timeout=1)

    out_text = "".join(captured_out)
    err_text = "".join(captured_err)
    return subprocess.CompletedProcess(
        proc.args,
        proc.returncode if proc.returncode is not None else 0,
        stdout=out_text,
        stderr=err_text,
    )


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


def poll_until(
    check_fn: Callable[[], bool],
    timeout_sec: int,
    check_interval_sec: int = 10,
    heartbeat_interval_sec: Optional[int] = None,
    heartbeat_message_fn: Optional[Callable[[int], str]] = None,
) -> bool:
    """
    Poll check_fn until it returns True or timeout. Reusable retry/poll pattern.
    On failure: check_fn returns False; we sleep and retry. On success: return True.
    Raises: if check_fn raises (e.g. non-retriable error), propagate up.
    """
    interval = heartbeat_interval_sec or DEFAULT_HEARTBEAT_INTERVAL_SEC
    start = time.time()
    last_heartbeat = 0
    while (time.time() - start) < timeout_sec:
        try:
            if check_fn():
                return True
        except Exception:
            raise
        elapsed = int(time.time() - start)
        if heartbeat_message_fn and elapsed - last_heartbeat >= interval and elapsed > 0:
            logger.info(heartbeat_message_fn(elapsed))
            last_heartbeat = elapsed
        time.sleep(min(check_interval_sec, interval))
    return False
