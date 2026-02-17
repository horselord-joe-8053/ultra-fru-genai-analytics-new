"""
Image tag generation for backend container (mirrors legacy git_helpers.sh).

Format: fru_<env>_<date>_<sha>_<slug> (clean) or fru_<env>_<date>_<sha>_dirty_<timestamp> (dirty)
"""
import os
import re
import subprocess
from datetime import datetime


def generate_image_tag(env: str | None = None) -> str:
    """
    Generate image tag from git commit. Falls back to timestamp if not in git.
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
        return f"fru_{env}_{datetime.utcnow().strftime('%Y%m%d')}_build_{ts}"

    commit_date = ""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d", "HEAD"],
            text=True,
            cwd=os.getcwd(),
        )
        commit_date = out.strip() or datetime.utcnow().strftime("%Y%m%d")
    except Exception:
        commit_date = datetime.utcnow().strftime("%Y%m%d")

    base_sha = ""
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
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"fru_{env}_{commit_date}_{base_sha}_dirty_{ts}"

    commit_msg = "unknown"
    try:
        commit_msg = subprocess.check_output(
            ["git", "log", "-1", "--format=%s", "HEAD"],
            text=True,
            cwd=os.getcwd(),
        ).strip()
    except Exception:
        pass

    slug = commit_msg.lower()
    slug = re.sub(r"[^a-z0-9._ -]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")[:30] or "commit"

    return f"fru_{env}_{commit_date}_{base_sha}_{slug}"


def get_container_image_tags(version_tag: str, include_latest: bool = True) -> str:
    """Comma-separated tags for CONTAINER_IMAGE_TAGS env (e.g. 'fru_dev_...,latest')."""
    if include_latest:
        return f"{version_tag},latest"
    return version_tag
