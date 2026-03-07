#!/usr/bin/env python3
"""
Local verify: check API endpoints (assumes API is running on localhost:5001).

Usage:
  python orchestrator.py verify --provider local

Prerequisite: Start API with PORT=5001 PYTHONPATH=core_app python -m backend.api.app
"""
import os
import sys

import requests

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()

BASE_URL = os.environ.get("LOCAL_API_URL", "http://localhost:5001")


def main() -> int:
    logger.step("Local verify")

    ok = True

    # Health
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            logger.success("/health OK")
        else:
            logger.error(f"/health returned {r.status_code}")
            ok = False
    except Exception as e:
        logger.error(f"/health unreachable: {e}. Is API running? (PORT=5001 PYTHONPATH=core_app python -m backend.api.app)")
        ok = False

    # Version
    try:
        r = requests.get(f"{BASE_URL}/version", timeout=5)
        if r.status_code == 200:
            logger.success("/version OK")
        else:
            logger.error(f"/version returned {r.status_code}")
            ok = False
    except Exception as e:
        logger.error(f"/version unreachable: {e}")
        ok = False

    # Rawdata
    try:
        r = requests.get(f"{BASE_URL}/rawdata?limit=5", timeout=5)
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            logger.success(f"/rawdata OK (total={total})")
        else:
            logger.error(f"/rawdata returned {r.status_code}")
            ok = False
    except Exception as e:
        logger.error(f"/rawdata unreachable: {e}")
        ok = False

    # Analytics
    try:
        r = requests.get(f"{BASE_URL}/analytics", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "error" in data:
                logger.warning(f"/analytics: {data['error']}")
            else:
                logger.success(f"/analytics OK (total_records={data.get('total_records', '?')})")
        else:
            logger.error(f"/analytics returned {r.status_code}")
            ok = False
    except Exception as e:
        logger.error(f"/analytics unreachable: {e}")
        ok = False

    if ok:
        logger.success("Local verify complete")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
