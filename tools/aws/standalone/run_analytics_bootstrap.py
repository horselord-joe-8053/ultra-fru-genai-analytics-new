#!/usr/bin/env python3
"""
Run analytics bootstrap (Spark run_analytics) and wait for completion.

Use when /analytics shows "No analytics data available yet" and you want to
populate batch_analytics immediately.

Usage:
  python tools/aws/standalone/run_analytics_bootstrap.py --env dev
  python tools/aws/standalone/run_analytics_bootstrap.py --env dev --region us-east-2
  python tools/aws/standalone/run_analytics_bootstrap.py --env dev --no-wait  # fire-and-forget

Prerequisites:
  - Deploy completed (nonkube stack applied)
  - setup_database ran (fru_sales_raw populated from CSV)
  - Aurora reachable from ECS tasks (aurora_from_ecs SG rule)
"""
import argparse
import os
import sys

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.deploy.deploy_common import run_ecs_bootstrap

load_dotenv()


def main():
    ap = argparse.ArgumentParser(description="Run analytics bootstrap (Spark run_analytics)")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    ap.add_argument("--no-wait", action="store_true", help="Start task and return immediately")
    args = ap.parse_args()

    run_ecs_bootstrap(env=args.env, region=args.region)


if __name__ == "__main__":
    main()
