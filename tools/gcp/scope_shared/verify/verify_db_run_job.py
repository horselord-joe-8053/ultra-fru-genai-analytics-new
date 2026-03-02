#!/usr/bin/env python3
"""
Verify GCP Cloud Run Job (schema + load_data) by running the job and checking record count.

Thin wrapper over tools/gcp/scope_shared/deploy/db_setup/cloud_job.run_and_verify().
Same path as deploy; idempotent for mixed runs.

Reference data: core_app/data/raw/fridge_sales_with_rating.csv (201 rows).

Usage:
  python tools/gcp/scope_shared/verify/verify_db_run_job.py --env dev --region us-central1
"""
import argparse
import os
import sys

from tools.cloud_shared.env import load_dotenv

load_dotenv()


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify Cloud Run Job (schema + load_data) via record count")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=os.getenv("CLOUD_REGION", "us-central1"))
    ap.add_argument("--force-refresh-data", action="store_true", help="Force reload before verify")
    args = ap.parse_args()

    from tools.cloud_shared.logging import logger
    from tools.gcp.scope_shared.core.backend import resolve_region
    from tools.gcp.scope_shared.deploy.db_setup.cloud_job import run_and_verify

    try:
        region = resolve_region(args.region)
        ok = run_and_verify(args.env, region, force=args.force_refresh_data)
        return 0 if ok else 1
    except Exception as e:
        logger.error(f"Verify DB run job failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
