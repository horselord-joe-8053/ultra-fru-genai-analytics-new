"""
Minimal logger for analytics jobs. Writes to stdout/stderr with flush for CloudWatch visibility.
No external deps; Spark image only has jobs/ copied, so tools.cloud_shared is unavailable.
"""
import sys
from datetime import datetime


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _emit(level: str, msg: str, *, file=sys.stdout) -> None:
    print(f"[{_ts()}] [{level}] {msg}", file=file, flush=True)


def info(msg: str) -> None:
    _emit("INFO", msg)


def success(msg: str) -> None:
    _emit("SUCCESS", msg)


def warning(msg: str) -> None:
    _emit("WARNING", msg)


def error(msg: str) -> None:
    _emit("ERROR", msg, file=sys.stderr)


def step(msg: str) -> None:
    print(f"\n[{_ts()}] [STEP] {msg}", flush=True)
