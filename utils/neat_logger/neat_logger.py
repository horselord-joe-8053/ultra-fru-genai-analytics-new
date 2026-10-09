from __future__ import annotations

import datetime
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional, TextIO

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
VIOLET = '\033[38;5;129m'  # 256-color violet for phase/operation boundaries / HEARTBEAT tag
NC = '\033[0m'

_ANSI_ESC = re.compile(r"\033\[[0-9;]*m")

_THIS_DIR = Path(__file__).resolve().parent
_FALLBACK_YAML = _THIS_DIR / "neat_logger_fallback_config.yaml"
_LEGACY_YAML = _THIS_DIR / "neat_logger_config.yaml"
_CONFIG_JSON_LEGACY = Path(__file__).with_name("neat_logger_config.json")

_file_lock = threading.Lock()
_cached_file_path: Optional[Path] = None
_file_fp: Optional[TextIO] = None


def _intrinsic_repo_root() -> Path:
    """``portuguese-learn/`` from ``utils/neat_logger/neat_logger.py`` layout."""
    return Path(__file__).resolve().parents[2]


def _overlay_neat_logger_env(base: dict) -> dict:
    """Merge optional env overrides (same keys as YAML)."""
    out = dict(base)
    root = str(os.getenv("NEAT_LOGGER_LOG_ROOT", "")).strip()
    if root:
        out["log_root"] = root
    out_mode = str(os.getenv("NEAT_LOGGER_LOG_OUTPUT", "")).strip()
    if out_mode in ("stdout", "file", "both"):
        out["log_output"] = out_mode
    fname = str(os.getenv("NEAT_LOGGER_LOG_FILE_NAME", "")).strip()
    if fname:
        out["log_file_name"] = fname
    hb = str(os.getenv("NEAT_LOGGER_HEARTBEAT_INTERVAL_SEC", "")).strip()
    if hb:
        try:
            out["heartbeat_interval_sec"] = float(hb)
        except ValueError:
            pass
    return out


def _load_yaml_dict(path: Path) -> dict:
    try:
        import yaml  # optional; repo API venv includes PyYAML

        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_raw_config() -> dict:
    """Load ``neat_logger_fallback_config.yaml``, else legacy ``neat_logger_config.yaml``, then env."""
    base: dict = {}
    if _FALLBACK_YAML.is_file():
        base = _load_yaml_dict(_FALLBACK_YAML)
    elif _LEGACY_YAML.is_file():
        base = _load_yaml_dict(_LEGACY_YAML)
    if not base and _CONFIG_JSON_LEGACY.is_file():
        try:
            raw = _CONFIG_JSON_LEGACY.read_text(encoding="utf-8").strip()
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    base = data
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return _overlay_neat_logger_env(base)


_CONFIG = _load_raw_config()


def reload_config() -> None:
    """Re-read YAML/JSON, close file sink, reopen on next file write."""
    global _CONFIG, _cached_file_path, _file_fp
    with _file_lock:
        if _file_fp is not None:
            try:
                _file_fp.close()
            except OSError:
                pass
            _file_fp = None
            _cached_file_path = None
        _CONFIG = _load_raw_config()
    from .neat_logger_instance import rebuild_default_logger

    rebuild_default_logger()


def _heartbeat_interval_default() -> float:
    raw = _CONFIG.get("heartbeat_interval_sec", 20.0)
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return 20.0


def _heartbeat_badge() -> str:
    return f"{VIOLET}[HEARTBEAT]{NC}"


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


def _log_prefix_plain(level: str) -> str:
    return _ANSI_ESC.sub("", _log_prefix(level))


def _log_output_mode() -> str:
    env = str(os.getenv("NEAT_LOGGER_LOG_OUTPUT", "")).strip().lower()
    if env in ("stdout", "file", "both"):
        return env
    return str(_CONFIG.get("log_output", "stdout")).strip().lower()


def _resolved_log_root() -> Path:
    """``log_root`` is repo-relative unless absolute (see fallback YAML comments)."""
    raw = _CONFIG.get("log_root", "logs")
    p = Path(str(raw).strip() or "logs")
    if p.is_absolute():
        return p.resolve()
    rr = os.getenv("REPO_ROOT", "").strip()
    anchor = Path(rr).expanduser().resolve() if rr else _intrinsic_repo_root()
    return (anchor / p).resolve()


def _write_file_plain(line: str) -> None:
    global _cached_file_path, _file_fp
    mode = _log_output_mode()
    if mode not in ("file", "both"):
        return
    root = _resolved_log_root()
    root.mkdir(parents=True, exist_ok=True)
    fname = str(_CONFIG.get("log_file_name", "api.log")).strip() or "api.log"
    path = (root / fname).resolve()

    if _file_fp is not None and (_cached_file_path != path):
        try:
            _file_fp.close()
        except OSError:
            pass
        _file_fp = None

    if _file_fp is None:
        _file_fp = open(path, "a", encoding="utf-8")  # noqa: SIM115 — long-lived sink
        _cached_file_path = path

    _file_fp.write(line)
    _file_fp.flush()


def _emit(level: str, msg: str, *, stream,) -> None:
    """Emit colored line to stream (stdout/stderr) and optionally plain line to api log file."""
    colored = f"{_log_prefix(level)}{msg}"
    plain = f"{_log_prefix_plain(level)}{msg}\n"

    mode = _log_output_mode()
    if mode in ("stdout", "both"):
        print(colored, file=stream, flush=True)

    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain)


def _emit_tty_plain(level: str, *, tty_msg: str, file_msg: str, stream) -> None:
    """Like ``_emit`` but stdout/stderr uses ``tty_msg`` (may include ANSI); file mirror uses plain ``file_msg``."""
    colored = f"{_log_prefix(level)}{tty_msg}"
    plain = f"{_log_prefix_plain(level)}{file_msg}\n"

    mode = _log_output_mode()
    if mode in ("stdout", "both"):
        print(colored, file=stream, flush=True)

    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain)


def info(msg: str) -> None:
    _emit("INFO", msg, stream=sys.stdout)


def info_tty_plain(*, tty_msg: str, file_msg: str) -> None:
    """INFO line with optional ANSI in ``tty_msg`` only; ``api.log`` (if enabled) stays plain."""
    _emit_tty_plain("INFO", tty_msg=tty_msg, file_msg=file_msg, stream=sys.stdout)


def error_tty_plain(*, tty_msg: str, file_msg: str) -> None:
    """ERROR line with optional ANSI in ``tty_msg`` only; ``api.log`` (if enabled) uses ``file_msg``."""
    _emit_tty_plain("ERROR", tty_msg=tty_msg, file_msg=file_msg, stream=sys.stderr)


def success(msg: str) -> None:
    _emit("SUCCESS", msg, stream=sys.stdout)


def warning(msg: str) -> None:
    _emit("WARNING", msg, stream=sys.stdout)


def error(msg: str) -> None:
    _emit("ERROR", msg, stream=sys.stderr)


def step(msg: str) -> None:
    """Highlighted step — file strip uses plain SUCCESS prefix + ascii arrow."""
    mode = _log_output_mode()
    colored = f"\n{_log_prefix('SUCCESS')}{GREEN}==>{NC} {BLUE}{msg}{NC}"
    plain = f"\n{_log_prefix_plain('SUCCESS')}==> {msg}\n"

    if mode in ("stdout", "both"):
        print(colored, file=sys.stdout, flush=True)

    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain)


def phase_start(phase_num: int, total: int, name: str) -> None:
    colored = (
        f"\n{_log_prefix('INFO')}{VIOLET}═══ [{phase_num}/{total}] {name} ── START{NC}"
    )
    plain = (
        f"\n{_log_prefix_plain('INFO')}═══ [{phase_num}/{total}] {name} ── START\n"
    )
    mode = _log_output_mode()
    if mode in ("stdout", "both"):
        print(colored, file=sys.stdout, flush=True)
    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain)


def phase_end(phase_num: int, total: int, name: str, duration_sec: int) -> None:
    dur = f"{duration_sec}s" if duration_sec < 60 else f"{duration_sec // 60}m{duration_sec % 60}s"
    colored = f"{_log_prefix('SUCCESS')}{VIOLET}═══ [{phase_num}/{total}] {name} ── DONE ({dur}){NC}"
    plain = f"{_log_prefix_plain('SUCCESS')}═══ [{phase_num}/{total}] {name} ── DONE ({dur})\n"
    mode = _log_output_mode()
    if mode in ("stdout", "both"):
        print(colored, file=sys.stdout, flush=True)
    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain)


def operation_start(operation: str, scope: str, env: str, region: str) -> None:
    colored = f"\n{_log_prefix('SUCCESS')}{VIOLET}═══ {operation} START: scope={scope} env={env} region={region} ═══{NC}"
    plain = (
        f"\n{_log_prefix_plain('SUCCESS')}═══ {operation} START: scope={scope} env={env} region={region} ═══\n"
    )
    mode = _log_output_mode()
    if mode in ("stdout", "both"):
        print(colored, file=sys.stdout, flush=True)
    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain)


def operation_end(operation: str, scope: str, env: str, region: str, duration_sec: int, ok: bool = True) -> None:
    dur = f"{duration_sec}s" if duration_sec < 60 else f"{duration_sec // 60}m{duration_sec % 60}s"
    status = "DONE" if ok else "FAILED"
    lvl = "SUCCESS" if ok else "ERROR"
    colored = (
        f"\n{_log_prefix(lvl)}{VIOLET}═══ {operation} {status}: scope={scope} env={env} region={region} ({dur}) ═══{NC}"
    )
    plain_v = (
        f"\n{_log_prefix_plain(lvl)}═══ {operation} {status}: scope={scope} env={env} region={region} ({dur}) ═══\n"
    )
    mode = _log_output_mode()
    stream_out = sys.stdout if ok else sys.stderr
    if mode in ("stdout", "both"):
        print(colored, file=stream_out, flush=True)
    if mode in ("file", "both"):
        with _file_lock:
            _write_file_plain(plain_v)


class Heartbeat:
    """
    Emit periodic progress lines while blocking work runs.

    Usage::

        with Heartbeat("pyannote diarize foo.wav"):
            pipeline(...)

    Default ``interval_sec`` is read from ``neat_logger_fallback_config.yaml``
    (``heartbeat_interval_sec``) when omitted (legacy JSON still supported if YAML is absent).
    """

    def __init__(
        self,
        message: str,
        *,
        interval_sec: Optional[float] = None,
        soft_wall_sec: Optional[float] = None,
        announce_complete: bool = True,
    ):
        self.message = message
        if interval_sec is None:
            self.interval_sec = _heartbeat_interval_default()
        else:
            self.interval_sec = max(1.0, float(interval_sec))
        self.soft_wall_sec = soft_wall_sec
        self.announce_complete = announce_complete

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[float] = None
        self._soft_wall_logged = False

    def _run(self) -> None:
        start_time = self._start_time
        if start_time is None:
            return
        while not self._stop_event.wait(self.interval_sec):
            if self._stop_event.is_set():
                break
            elapsed = int(time.time() - start_time)
            if (
                self.soft_wall_sec is not None
                and self.soft_wall_sec > 0
                and elapsed > self.soft_wall_sec
                and not self._soft_wall_logged
            ):
                warning(
                    f"{_heartbeat_badge()} Still running after {self.soft_wall_sec:.0f}s "
                    f"(soft wall): {self.message}"
                )
                self._soft_wall_logged = True
            info(f"{_heartbeat_badge()} {self.message} … ({elapsed}s elapsed)")

    def __enter__(self) -> "Heartbeat":
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self.interval_sec + 2.0)

        if self.announce_complete:
            start_time = self._start_time
            if start_time is not None:
                elapsed = int(time.time() - start_time)
                if exc_type:
                    error(f"Task failed: '{self.message}' (after {elapsed}s)")
                else:
                    success(f"Task completed: '{self.message}' (took {elapsed}s)")


# --- Default singleton (module API); class/factory in neat_logger_instance.py ---
from .neat_logger_instance import (  # noqa: E402
    NeatLogger,
    NeatLoggerConfig,
    NeatLoggerFactory,
    NeatLoggerHeartbeat,
    default_logger,
)


def _delegate_info(msg: str) -> None:
    default_logger().info(msg)


def _delegate_success(msg: str) -> None:
    default_logger().success(msg)


def _delegate_warning(msg: str) -> None:
    default_logger().warning(msg)


def _delegate_error(msg: str) -> None:
    default_logger().error(msg)


def _delegate_step(msg: str) -> None:
    default_logger().step(msg)


def _delegate_phase_start(phase_num: int, total: int, name: str) -> None:
    default_logger().phase_start(phase_num, total, name)


def _delegate_phase_end(phase_num: int, total: int, name: str, duration_sec: int) -> None:
    default_logger().phase_end(phase_num, total, name, duration_sec)


info = _delegate_info
success = _delegate_success
warning = _delegate_warning
error = _delegate_error
step = _delegate_step
phase_start = _delegate_phase_start
phase_end = _delegate_phase_end


class _ModuleHeartbeat:
    """Context manager delegating to the default ``NeatLogger`` instance."""

    def __init__(
        self,
        message: str,
        *,
        interval_sec: Optional[float] = None,
        soft_wall_sec: Optional[float] = None,
        announce_complete: bool = True,
    ) -> None:
        self._ctx = default_logger().heartbeat(
            message,
            interval_sec=interval_sec,
            soft_wall_sec=soft_wall_sec,
            announce_complete=announce_complete,
        )

    def __enter__(self) -> _ModuleHeartbeat:
        self._ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._ctx.__exit__(exc_type, exc_val, exc_tb)


Heartbeat = _ModuleHeartbeat
