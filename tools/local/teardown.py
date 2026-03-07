#!/usr/bin/env python3
"""
Local teardown: stop PostgreSQL and remove Spark volume.

Usage:
  python orchestrator.py teardown --provider local
"""
import os
import subprocess
import sys

from tools.cloud_shared.logging import logger

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE_FILE = "docker-compose.local.yml"
COMPOSE_PROJECT = "fru_local"


def main() -> int:
    logger.step("Local teardown")
    r = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "-p", COMPOSE_PROJECT, "down", "-v"],
        cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        logger.error("Teardown failed")
        return 1
    # Remove Spark delta volume
    subprocess.run(["docker", "volume", "rm", "fru_delta"], capture_output=True)
    logger.success("Local teardown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
