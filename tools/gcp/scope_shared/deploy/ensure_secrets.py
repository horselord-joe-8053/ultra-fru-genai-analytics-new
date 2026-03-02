"""
Ensure Secret Manager secret values (GCP). Thin wrapper around cloud_shared.

Usage:
  python tools/gcp/scope_shared/deploy/ensure_secrets.py --env dev
"""
import os
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.ensure_secrets import ensure_secrets

load_dotenv()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    from tools.gcp.scope_shared.core.backend import resolve_region
    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    try:
        ensure_secrets("gcp", args.env, region)
        sys.exit(0)
    except Exception as e:
        from tools.cloud_shared.logging import logger
        logger.error(f"[SECRETS] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
