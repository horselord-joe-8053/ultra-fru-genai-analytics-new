"""
Shared CSV helpers for verification.

Expected total records = line count minus header. Used by AWS and GCP verify_all_deploy.
"""
import os
import sys

from tools.cloud_shared.logging import logger


def _csv_path() -> str:
    """Path to fridge_sales_with_rating.csv (repo root relative)."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    return os.path.join(repo_root, "core_app", "data", "raw", "fridge_sales_with_rating.csv")


def get_total_rec_from_csv() -> int:
    """
    Return expected total records from CSV (line count minus header).
    Exits with 1 if CSV not found; verification requires it for QueryStream/analytics checks.
    """
    path = _csv_path()
    if not os.path.exists(path):
        logger.error(f"CSV not found: {path}")
        logger.error("Verification requires the source CSV to determine expected record count. Cannot proceed.")
        sys.exit(1)
    with open(path) as f:
        return max(0, sum(1 for _ in f) - 1)
