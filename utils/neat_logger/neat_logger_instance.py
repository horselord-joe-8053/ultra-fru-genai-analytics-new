"""Per-instance neat_logger: scoped log file, tag prefix, and Heartbeat."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TextIO

# Shared presentation helpers (no import from neat_logger — avoids cycles).
from .neat_logger import (  # noqa: F401 — re-export colors for tests
    BLUE,
    GREEN,
    NC,
    RED,
    VIOLET,
    YELLOW,
    _heartbeat_badge,
    _intrinsic_repo_root,
    _load_raw_config,
    _log_prefix,
    _log_prefix_plain,
)

_THIS_DIR = Path(__file__).resolve().parent


@dataclass
class NeatLoggerConfig:
    log_root: str = "logs"
    log_file_name: str = "api.log"
    log_output: str = "stdout"
    heartbeat_interval_sec: float = 20.0
    tag_prefix: str = ""

    @classmethod
    def from_global_yaml(cls) -> NeatLoggerConfig:
        raw = _load_raw_config()
        hb = raw.get("heartbeat_interval_sec", 20.0)
        try:
            hb_f = max(1.0, float(hb))
        except (TypeError, ValueError):
            hb_f = 20.0
        out_mode = str(raw.get("log_output", "stdout")).strip().lower() or "stdout"
        if out_mode not in ("stdout", "file", "both"):
            out_mode = "stdout"
        return cls(
            log_root=str(raw.get("log_root", "logs")).strip() or "logs",
            log_file_name=str(raw.get("log_file_name", "api.log")).strip() or "api.log",
            log_output=out_mode,
            heartbeat_interval_sec=hb_f,
            tag_prefix="",
        )


class NeatLogger:
    """Scoped CLI logger with optional tag prefix and dedicated log file."""

    def __init__(self, config: NeatLoggerConfig) -> None:
        self._config = config
        self._file_lock = threading.Lock()
        self._cached_file_path: Optional[Path] = None
        self._file_fp: Optional[TextIO] = None

    def _tag(self, msg: str) -> str:
        prefix = (self._config.tag_prefix or "").strip()
        return f"{prefix} {msg}" if prefix else msg

    def _log_output_mode(self) -> str:
        mode = self._config.log_output.strip().lower()
        return mode if mode in ("stdout", "file", "both") else "stdout"

    def _resolved_log_root(self) -> Path:
        p = Path(str(self._config.log_root).strip() or "logs")
        if p.is_absolute():
            return p.resolve()
        rr = os.getenv("REPO_ROOT", "").strip()
        anchor = Path(rr).expanduser().resolve() if rr else _intrinsic_repo_root()
        return (anchor / p).resolve()

    def _write_file_plain(self, line: str) -> None:
        if self._log_output_mode() not in ("file", "both"):
            return
        root = self._resolved_log_root()
        root.mkdir(parents=True, exist_ok=True)
        fname = (self._config.log_file_name or "api.log").strip() or "api.log"
        path = (root / fname).resolve()
        with self._file_lock:
            if self._file_fp is not None and self._cached_file_path != path:
                try:
                    self._file_fp.close()
                except OSError:
                    pass
                self._file_fp = None
            if self._file_fp is None:
                self._file_fp = open(path, "a", encoding="utf-8")  # noqa: SIM115
                self._cached_file_path = path
            self._file_fp.write(line)
            self._file_fp.flush()

    def _emit(self, level: str, msg: str, *, stream) -> None:
        body = self._tag(msg)
        colored = f"{_log_prefix(level)}{body}"
        plain = f"{_log_prefix_plain(level)}{body}\n"
        mode = self._log_output_mode()
        if mode in ("stdout", "both"):
            print(colored, file=stream, flush=True)
        if mode in ("file", "both"):
            self._write_file_plain(plain)

    def info(self, msg: str) -> None:
        self._emit("INFO", msg, stream=sys.stdout)

    def success(self, msg: str) -> None:
        self._emit("SUCCESS", msg, stream=sys.stdout)

    def warning(self, msg: str) -> None:
        self._emit("WARNING", msg, stream=sys.stdout)

    def error(self, msg: str) -> None:
        self._emit("ERROR", msg, stream=sys.stderr)

    def step(self, msg: str) -> None:
        body = self._tag(msg)
        mode = self._log_output_mode()
        colored = f"\n{_log_prefix('SUCCESS')}{GREEN}==>{NC} {BLUE}{body}{NC}"
        plain = f"\n{_log_prefix_plain('SUCCESS')}==> {body}\n"
        if mode in ("stdout", "both"):
            print(colored, file=sys.stdout, flush=True)
        if mode in ("file", "both"):
            self._write_file_plain(plain)

    def phase_start(self, phase_num: int, total: int, name: str) -> None:
        body = self._tag(f"═══ [{phase_num}/{total}] {name} ── START")
        colored = f"\n{_log_prefix('INFO')}{VIOLET}{body}{NC}"
        plain = f"\n{_log_prefix_plain('INFO')}{body}\n"
        mode = self._log_output_mode()
        if mode in ("stdout", "both"):
            print(colored, file=sys.stdout, flush=True)
        if mode in ("file", "both"):
            self._write_file_plain(plain)

    def phase_end(self, phase_num: int, total: int, name: str, duration_sec: int) -> None:
        dur = f"{duration_sec}s" if duration_sec < 60 else f"{duration_sec // 60}m{duration_sec % 60}s"
        body = self._tag(f"═══ [{phase_num}/{total}] {name} ── DONE ({dur})")
        colored = f"{_log_prefix('SUCCESS')}{VIOLET}{body}{NC}"
        plain = f"{_log_prefix_plain('SUCCESS')}{body}\n"
        mode = self._log_output_mode()
        if mode in ("stdout", "both"):
            print(colored, file=sys.stdout, flush=True)
        if mode in ("file", "both"):
            self._write_file_plain(plain)

    def heartbeat(
        self,
        message: str,
        *,
        interval_sec: Optional[float] = None,
        soft_wall_sec: Optional[float] = None,
        announce_complete: bool = False,
    ) -> NeatLoggerHeartbeat:
        return NeatLoggerHeartbeat(
            self,
            message,
            interval_sec=interval_sec,
            soft_wall_sec=soft_wall_sec,
            announce_complete=announce_complete,
        )


class NeatLoggerHeartbeat:
    def __init__(
        self,
        logger: NeatLogger,
        message: str,
        *,
        interval_sec: Optional[float] = None,
        soft_wall_sec: Optional[float] = None,
        announce_complete: bool = True,
    ) -> None:
        self._logger = logger
        self.message = message
        if interval_sec is None:
            self.interval_sec = logger._config.heartbeat_interval_sec
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
        badge = _heartbeat_badge()
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
                self._logger.warning(
                    f"{badge} Still running after {self.soft_wall_sec:.0f}s "
                    f"(soft wall): {self.message}"
                )
                self._soft_wall_logged = True
            self._logger.info(f"{badge} {self.message} … ({elapsed}s elapsed)")

    def __enter__(self) -> NeatLoggerHeartbeat:
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
                    self._logger.error(f"Task failed: '{self.message}' (after {elapsed}s)")
                else:
                    self._logger.success(f"Task completed: '{self.message}' (took {elapsed}s)")


# Type aliases for plan/docs (all are ``NeatLogger`` instances).
ApiNeatLogger = NeatLogger
OpsRunTestsLogger = NeatLogger
OpsRunAllLogger = NeatLogger


class NeatLoggerFactory:
    """Central factory: shared role loggers (one file per role) + optional ``create`` escape hatch."""

    _api: Optional[NeatLogger] = None
    _ops_run_all_by_component: dict[str, NeatLogger] = {}
    _ops_run_tests_by_component: dict[str, NeatLogger] = {}

    @classmethod
    def _normalize_component(cls, component: str) -> str:
        return (component or "MAIN").strip().upper().replace(" ", "_")

    @classmethod
    def api(cls, **overrides: object) -> ApiNeatLogger:
        """**ApiNeatLogger** — FastAPI and ``apps/api`` callers. File: ``logs/api.log`` (YAML defaults)."""
        if cls._api is None:
            cfg = NeatLoggerConfig.from_global_yaml()
            cfg.tag_prefix = ""
            for key, val in overrides.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, val)
            cls._api = NeatLogger(cfg)
        return cls._api

    @classmethod
    def ops_run_tests(cls, component: str, **overrides: object) -> OpsRunTestsLogger:
        """**OpsRunTestsLogger** — test rituals only (``resall``, ``all-test`` runner, …).

        Shared file: ``logs/ops/run_tests_only.log``. Tag: ``[OPS][<COMPONENT>]`` (e.g. ``RESALL_RUNNER``).
        """
        key = cls._normalize_component(component)
        if key not in cls._ops_run_tests_by_component:
            cfg = NeatLoggerConfig.from_global_yaml()
            cfg.log_root = "logs/ops"
            cfg.log_file_name = "run_tests_only.log"
            cfg.log_output = "both"
            cfg.tag_prefix = f"[OPS][{key}]"
            for k, val in overrides.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, val)
            cls._ops_run_tests_by_component[key] = NeatLogger(cfg)
        return cls._ops_run_tests_by_component[key]

    @classmethod
    def ops_run_all(cls, component: str = "RUN_ALL", **overrides: object) -> OpsRunAllLogger:
        """**OpsRunAllLogger** — ``run_all.py`` entry (start/stop/restart/e2e-test dispatch).

        Shared file: ``logs/ops/run_all.log``. Tag: ``[OPS][<COMPONENT>]`` (default ``RUN_ALL``).
        """
        key = cls._normalize_component(component)
        if key not in cls._ops_run_all_by_component:
            cfg = NeatLoggerConfig.from_global_yaml()
            cfg.log_root = "logs/ops"
            cfg.log_file_name = "run_all.log"
            cfg.log_output = "both"
            cfg.tag_prefix = f"[OPS][{key}]"
            for k, val in overrides.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, val)
            cls._ops_run_all_by_component[key] = NeatLogger(cfg)
        return cls._ops_run_all_by_component[key]

    @classmethod
    def create(cls, scope: str, component: str, **overrides: object) -> NeatLogger:
        """Escape hatch when role helpers do not fit. Prefer ``api`` / ``ops_run_tests`` / ``ops_run_all``."""
        scope_u = (scope or "API").strip().upper()
        if scope_u == "API":
            return cls.api(**overrides)
        comp = cls._normalize_component(component)
        cfg = NeatLoggerConfig.from_global_yaml()
        if scope_u == "OPS":
            cfg.log_root = "logs/ops"
            cfg.log_file_name = "ops.log"
            cfg.tag_prefix = f"[OPS][{comp}]"
        else:
            cfg.log_file_name = "tests.log"
            cfg.tag_prefix = f"[TEST][{comp}]"
        for key, val in overrides.items():
            if hasattr(cfg, key):
                setattr(cfg, key, val)
        return NeatLogger(cfg)


_default_instance: Optional[NeatLogger] = None


def default_logger() -> ApiNeatLogger:
    """Module ``from utils.neat_logger import logger`` uses the shared **ApiNeatLogger**."""
    global _default_instance
    if _default_instance is None:
        _default_instance = NeatLoggerFactory.api()
    return _default_instance


def rebuild_default_logger() -> ApiNeatLogger:
    global _default_instance
    NeatLoggerFactory._api = None
    _default_instance = NeatLoggerFactory.api()
    return _default_instance
