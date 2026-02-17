#!/usr/bin/env python3
"""
Diagnose API database and agent connectivity.

Usage:
  python tools/aws/temp_one_off/diagnose_api_db.py --base-url https://your-cloudfront-domain
  python tools/aws/temp_one_off/diagnose_api_db.py --base-url http://alb-dns-name  # direct ALB

Helps narrow down:
- /analytics "Database not configured or unreachable"
- /query/stream "Agent-based query processing is disabled"
"""
import argparse
import json
import os
import sys

import requests

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv

load_dotenv()


def main():
    ap = argparse.ArgumentParser(description="Diagnose API DB and agent connectivity")
    ap.add_argument("--base-url", required=True, help="Base URL (e.g. https://xxx.cloudfront.net or http://alb-dns)")
    ap.add_argument("--timeout", type=int, default=10)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    logger.step(f"Diagnosing API at {base}")

    # 1. Health - most important: shows DB status
    try:
        r = requests.get(f"{base}/health", timeout=args.timeout)
        r.raise_for_status()
        data = r.json()
        db_status = data.get("database", "unknown")
        db_err = data.get("database_error", "")
        if db_status == "connected":
            logger.success("✓ Database: connected")
        else:
            logger.error(f"✗ Database: {db_status}")
            if db_err:
                logger.error(f"  Error: {db_err}")
            logger.info("  → Fix: Ensure PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD reach API container")
            logger.info("  → Nonkube: Check ECS task env_vars + secret_arns (db_password_plain)")
            logger.info("  → Kube: Check deployment env + db-credentials secret")
            logger.info("  → Run: python tools/aws/common/deploy/ensure_secrets.py --env $FRU_ENV")
    except Exception as e:
        logger.error(f"✗ /health failed: {e}")
        sys.exit(1)

    # 2. Analytics
    try:
        r = requests.get(f"{base}/analytics", timeout=args.timeout)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        err = body.get("error", "")
        if err:
            if "PGHOST not set" in err:
                logger.error("✗ /analytics: PGHOST not set in API container")
            elif "unreachable" in err.lower():
                logger.error("✗ /analytics: DB unreachable (check SG, subnet, credentials)")
            elif "No analytics data" in err:
                logger.info("⚠ /analytics: DB connected but batch_analytics empty")
                logger.info("  → Run bootstrap: Spark task must run run_analytics.py and populate batch_analytics")
                logger.info("  → Check CloudWatch /fru/{env}/spark for 'fru bootstrap success'")
            else:
                logger.error(f"✗ /analytics: {err}")
        else:
            logger.success("✓ /analytics: OK")
    except Exception as e:
        logger.error(f"✗ /analytics request failed: {e}")

    # 3. Query stream (agent)
    try:
        r = requests.get(f"{base}/query/stream?query=test", timeout=args.timeout, stream=True)
        chunk = next(r.iter_content(decode_unicode=True, chunk_size=4096), "") or ""
        if "Agent-based query processing is disabled" in chunk:
            logger.error("✗ /query/stream: Agent disabled")
            logger.info("  → Agent needs: USE_AGENT_QUERY=true + DB connected + OPENAI_API_KEY")
            logger.info("  → If DB is disconnected, agent init fails (init_agent requires _connection_pool)")
        else:
            logger.success("✓ /query/stream: Agent reachable")
    except Exception as e:
        logger.error(f"✗ /query/stream request failed: {e}")

    logger.info("")
    logger.info("Next steps if DB disconnected:")
    logger.info("  1. python tools/aws/common/deploy/ensure_secrets.py --env $FRU_ENV  # set PGPASSWORD in Secrets Manager")
    logger.info("  2. Redeploy or force new ECS task / K8s rollout to pick up env")
    logger.info("  3. Nonkube: Verify ECS task has PGHOST from durable aurora_endpoint")
    logger.info("  4. Kube: Verify aurora_from_eks SG rule allows EKS nodes → Aurora 5432")


if __name__ == "__main__":
    main()
