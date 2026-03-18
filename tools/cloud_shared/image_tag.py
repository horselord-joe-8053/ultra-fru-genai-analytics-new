"""
Image tag generation for backend containers (shared across AWS and GCP).

Format: fru_<env>_<date>_<sha>_<slug> (clean)
    or: fru_<env>_<date>_<sha>_dirty_<timestamp>_<tz> (dirty)

Shared across AWS and GCP.
"""
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone


def _parse_git_commit_ci(ci_str: str) -> tuple[str, timedelta] | None:
    """
    Parse git %ci output: "2026-03-17 01:39:43 +0800" -> (commit_date YYYYMMDD, tz_offset).
    Returns None if unparseable.
    """
    if not ci_str or len(ci_str) < 20:
        return None
    ci_str = ci_str.strip()
    # Format: YYYY-MM-DD HH:MM:SS +0800 or -0500
    try:
        date_part = ci_str[:10].replace("-", "")  # YYYYMMDD
        tz_part = ci_str[-5:]  # +0800 or -0500
        if tz_part[0] not in "+-" or len(tz_part) != 5:
            return None
        sign = 1 if tz_part[0] == "+" else -1
        h = int(tz_part[1:3]) * sign
        m = int(tz_part[3:5]) * sign
        offset = timedelta(hours=h, minutes=m)
        return (date_part, offset)
    except (ValueError, IndexError):
        return None


def _format_tz_suffix(offset: timedelta) -> str:
    """Format timezone for tag suffix (Docker-safe: [a-zA-Z0-9_.-]). UTC or p0800 or m0500."""
    if offset == timedelta(0):
        return "UTC"
    total_secs = offset.total_seconds()
    prefix = "p" if total_secs >= 0 else "m"
    h = int(abs(total_secs) // 3600)
    m = int((abs(total_secs) % 3600) // 60)
    return f"{prefix}{h:02d}{m:02d}"


def generate_image_tag(env: str | None = None) -> str:
    """
    Generate image tag from git commit. Falls back to timestamp if not in git.
    commit_date and timestamp use the same timezone (from git committer).
    """
    env = (env or os.getenv("FRU_ENV", "dev")).lower()
    env = re.sub(r"[^a-z0-9]", "", env) or "dev"

    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            cwd=os.getcwd(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"fru_{env}_{datetime.utcnow().strftime('%Y%m%d')}_build_{ts}_UTC"

    # Get commit date and timezone from %ci (committer date with timezone)
    commit_date = datetime.utcnow().strftime("%Y%m%d")
    tz_offset = timedelta(0)
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ci", "HEAD"],
            text=True,
            cwd=os.getcwd(),
        )
        parsed = _parse_git_commit_ci(out)
        if parsed:
            commit_date, tz_offset = parsed
    except Exception:
        pass

    try:
        base_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            cwd=os.getcwd(),
        ).strip()
    except Exception:
        base_sha = "unknown"

    dirty = False
    try:
        subprocess.run(
            ["git", "diff", "--quiet"],
            capture_output=True,
            check=True,
            cwd=os.getcwd(),
        )
        subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True,
            check=True,
            cwd=os.getcwd(),
        )
    except subprocess.CalledProcessError:
        dirty = True

    if dirty:
        tz = timezone(tz_offset)
        ts = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
        tz_str = _format_tz_suffix(tz_offset)
        return f"fru_{env}_{commit_date}_{base_sha}_dirty_{ts}_{tz_str}"

    try:
        commit_msg = subprocess.check_output(
            ["git", "log", "-1", "--format=%s", "HEAD"],
            text=True,
            cwd=os.getcwd(),
        ).strip()
    except Exception:
        commit_msg = "unknown"

    slug = commit_msg.lower()
    slug = re.sub(r"[^a-z0-9._ -]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")[:30] or "commit"

    return f"fru_{env}_{commit_date}_{base_sha}_{slug}"


__all__ = ["generate_image_tag"]
