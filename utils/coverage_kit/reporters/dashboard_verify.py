"""HTTP smoke checks for the stitched coverage dashboard (Stage 1)."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class HttpCheck:
    path: str
    needle: str


_DEFAULT_CHECKS: tuple[HttpCheck, ...] = (
    HttpCheck("/", "Code coverage"),
    HttpCheck("/code-coverage/", "Code coverage"),
    HttpCheck("/", "panel-overview"),
)


def verify_dashboard_http(
    base_url: str,
    *,
    checks: tuple[HttpCheck, ...] = _DEFAULT_CHECKS,
    timeout_s: float = 5.0,
) -> tuple[int, list[str]]:
    """GET dashboard paths; return exit code and log lines."""
    lines: list[str] = []
    root = base_url.rstrip("/") + "/"
    failures = 0
    for check in checks:
        url = root + check.path.lstrip("/")
        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                status = resp.getcode()
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            failures += 1
            lines.append(f"[cov-dashboard] FAIL {check.path} HTTP {exc.code}")
            continue
        except OSError as exc:
            failures += 1
            lines.append(f"[cov-dashboard] FAIL {check.path} {exc}")
            continue
        if status != 200:
            failures += 1
            lines.append(f"[cov-dashboard] FAIL {check.path} status {status}")
            continue
        if check.needle not in body:
            failures += 1
            lines.append(
                f"[cov-dashboard] FAIL {check.path} missing substring {check.needle!r}"
            )
            continue
        lines.append(f"[cov-dashboard] OK {check.path} ({status})")
    if failures:
        lines.append(f"[cov-dashboard] HTTP checks failed: {failures}")
        return 1, lines
    lines.append("[cov-dashboard] HTTP checks passed")
    return 0, lines
