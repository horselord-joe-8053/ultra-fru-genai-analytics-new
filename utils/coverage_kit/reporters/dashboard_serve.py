"""HTTP helpers for the stitched coverage dashboard (Stage 1).

**Production:** ``ops/local/run_cov_dashboard.py`` spawns
``dashboard_serve_foreground`` as a detached process so **:5199** stays up after
``cov-finalize`` / ``resall --cov`` exit.

**In-process:** ``start_dashboard_server`` (daemon thread) remains for kit unit tests
and portable copies that do not wire ``run_cov_dashboard`` — do not use from
``finalize_coverage`` in this repo.
"""

from __future__ import annotations

import json
import socketserver
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class _DashboardServer:
    """Background ``ThreadingHTTPServer`` for dashboard htdocs."""

    def __init__(self, htdocs: Path, *, bind: str, port: int) -> None:
        self.htdocs = htdocs.resolve()
        self.bind = bind
        self.port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.htdocs))
        self._httpd = ThreadingHTTPServer((self.bind, self.port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None


_active_server: _DashboardServer | None = None


def write_session_marker(
    marker_path: Path,
    *,
    bind: str,
    port: int,
    dashboard_url: str,
) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ritual": "resall --cov",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "bind": bind,
        "port": port,
        "url": dashboard_url,
        "code_coverage_path": "/code-coverage/",
    }
    marker_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def start_dashboard_server(
    htdocs: Path,
    *,
    bind: str,
    port: int,
    marker_path: Path,
) -> str:
    """Start server (idempotent per process); return base URL."""
    global _active_server
    if _active_server is not None:
        try:
            _active_server.stop()
        except Exception:
            pass
        _active_server = None

    server = _DashboardServer(htdocs, bind=bind, port=port)
    server.start()
    _active_server = server
    url = f"http://{bind}:{port}/"
    write_session_marker(marker_path, bind=bind, port=port, dashboard_url=url)
    return url


def session_is_valid(marker_path: Path) -> bool:
    return marker_path.is_file()


def dashboard_base_url(*, bind: str, port: int) -> str:
    return f"http://{bind}:{port}/"


def is_dashboard_http_alive(*, bind: str, port: int, timeout_s: float = 2.0) -> bool:
    """True when the dashboard root responds with HTTP 200."""
    import urllib.error
    import urllib.request

    url = dashboard_base_url(bind=bind, port=port)
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return resp.getcode() == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def ensure_cov_dashboard_server(
    htdocs: Path,
    *,
    bind: str,
    port: int,
    marker_path: Path,
    restart: bool = False,
) -> tuple[str | None, list[str]]:
    """In-process start (daemon thread). Prefer ``run_cov_dashboard`` in this repo."""
    lines: list[str] = []
    if not (htdocs / "index.html").is_file():
        lines.append(
            "[cov-dashboard] missing tests/coverage/artifacts/backend/dashboard/htdocs/index.html "
            "(run resall --cov first)"
        )
        return None, lines
    url = dashboard_base_url(bind=bind, port=port)
    alive = is_dashboard_http_alive(bind=bind, port=port)
    if alive and not restart:
        lines.append(f"[cov-dashboard] dashboard already serving at {url}")
        return url, lines
    if alive and restart:
        global _active_server
        if _active_server is not None:
            try:
                _active_server.stop()
            except Exception:
                pass
            _active_server = None
    started = start_dashboard_server(htdocs, bind=bind, port=port, marker_path=marker_path)
    lines.append(f"[cov-dashboard] dashboard serving at {started}")
    return started, lines
