#!/usr/bin/env python3
"""
Local doctor: preflight checks for local deploy.

Usage:
  python orchestrator.py doctor --provider local
"""
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()


def main() -> int:
    logger.step("Local doctor (preflight)")

    errors = []

    # Docker
    r = subprocess.run(["docker", "info"], capture_output=True)
    if r.returncode != 0:
        errors.append("Docker not running or not installed")

    # Required env
    for var in ["PGPASSWORD", "OPENAI_API_KEY"]:
        if not os.environ.get(var):
            errors.append(f"{var} not set (check .env)")

    # Optional but recommended
    if not os.environ.get("CLAUDE_API_KEY") and not os.environ.get("GOOGLE_AI_API_KEY"):
        logger.warning("No CLAUDE_API_KEY or GOOGLE_AI_API_KEY; set CLOUD_PROVIDER=local and CLAUDE_API_KEY for /query")

    # CSV exists
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    csv_path = os.path.join(project_root, "core_app", "data", "raw", "fridge_sales_with_rating.csv")
    if not os.path.exists(csv_path):
        errors.append(f"CSV not found: {csv_path}")

    if errors:
        for e in errors:
            logger.error(e)
        return 1

    logger.success("Preflight OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
