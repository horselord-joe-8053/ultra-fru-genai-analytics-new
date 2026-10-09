"""Long-running coverage dashboard HTTP server (child process of ``run_cov_dashboard``).

Unlike the in-process ``dashboard_serve._DashboardServer`` (daemon thread tied to a
short-lived CLI), this module blocks in ``serve_forever`` so the parent ``run_all``
start/stop lifecycle can keep **:5199** alive after ``cov-finalize`` / ``resall --cov`` exit.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _write_marker(marker_path: Path, *, bind: str, port: int, url: str) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ritual": "persistent cov-dashboard",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "bind": bind,
        "port": port,
        "url": url,
        "code_coverage_path": "/code-coverage/",
        "mode": "persistent",
    }
    marker_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def serve_forever(
    htdocs: Path,
    *,
    bind: str,
    port: int,
    marker_path: Path,
) -> None:
    """Block until interrupted; serve ``htdocs`` with a threading HTTP server."""
    root = htdocs.resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"[cov-dashboard] missing {root / 'index.html'}")

    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    httpd = ThreadingHTTPServer((bind, port), handler)
    url = f"http://{bind}:{port}/"
    _write_marker(marker_path, bind=bind, port=port, url=url)
    print(f"[cov-dashboard] serving {url} (htdocs={root})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foreground coverage dashboard HTTP server.")
    parser.add_argument("--htdocs", type=Path, required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5199)
    parser.add_argument("--marker-path", type=Path, required=True)
    ns = parser.parse_args(argv)
    serve_forever(ns.htdocs, bind=ns.bind, port=ns.port, marker_path=ns.marker_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
