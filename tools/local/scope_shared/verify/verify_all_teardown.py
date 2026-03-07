#!/usr/bin/env python3
"""
Local teardown verify: ensure containers are down.
"""
import subprocess
import sys

from tools.cloud_shared.logging import logger

COMPOSE_PROJECT = "fru_local"


def main() -> int:
    r = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if "fru-postgres" in r.stdout:
        logger.warning("fru-postgres container still running")
        return 1
    logger.success("Local teardown verify OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
