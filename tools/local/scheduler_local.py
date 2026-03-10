#!/usr/bin/env python3
"""
Local analytics scheduler: runs batch analytics job every ANALYTICS_SCHEDULER_INTERVAL_SECONDS.

Local-only. Invokes run_analytics.py via docker run fru-spark:local.
Cloud uses CronJob/EventBridge/Cloud Scheduler instead.

Usage:
  ENABLE_ANALYTICS_SCHEDULER=true python tools/local/scheduler_local.py

Requires: ANALYTICS_SCHEDULER_INTERVAL_SECONDS in .env (no default; fail-fast if missing)
"""
import os
import subprocess
import sys
import time

from tools.cloud_shared.analytics_schedule import get_required_analytics_scheduler_interval_seconds
from tools.cloud_shared.env import load_dotenv, require

load_dotenv()

# Project root (parent of tools)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _run_analytics_job() -> int:
    """
    Run Spark analytics job (run_analytics.py) via docker run fru-spark:local.
    """
    pw = os.environ.get("PGPASSWORD", "")
    if not pw:
        return 1
    compose_project = os.environ.get("COMPOSE_PROJECT", "fru_local")
    delta_pkg = require("DELTA_LAKE_PACKAGE")
    storage_pkg = require("DELTA_STORAGE_PACKAGE")
    packages = f"{delta_pkg},{storage_pkg}"
    spark_cmd = [
        "docker", "run", "--rm",
        "--user", "root",
        "--network", f"{compose_project}_default",
        "-e", "PGHOST=postgres",
        "-e", "PGPORT=5432",
        "-e", "PGUSER=postgres",
        "-e", f"PGPASSWORD={pw}",
        "-e", f"PGDATABASE={os.environ.get('PGDATABASE', 'fru_db')}",
        "-e", "DELTA_TABLE_PATH=file:///tmp/delta/fru_sales",
        "-v", "fru_delta:/tmp/delta",
        "fru-spark:local",
        "/opt/spark/bin/spark-submit",
        "--packages", packages,
        "--conf", "spark.driver.extraJavaOptions=-Duser.home=/tmp",
        "--conf", "spark.executor.extraJavaOptions=-Duser.home=/tmp",
        "/opt/fru/jobs/run_analytics.py",
    ]
    r = subprocess.run(spark_cmd, cwd=_PROJECT_ROOT)
    return r.returncode


def main() -> int:
    if os.environ.get("ENABLE_ANALYTICS_SCHEDULER", "").lower() not in ("true", "1", "yes"):
        return 0
    interval_sec = get_required_analytics_scheduler_interval_seconds()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Scheduler started (interval={interval_sec}s)", flush=True)
    run_num = 0
    while True:
        run_num += 1
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Run #{run_num} starting...", flush=True)
        rc = _run_analytics_job()
        if rc != 0:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Run #{run_num} FAILED (exit {rc})", flush=True)
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Run #{run_num} OK", flush=True)
        time.sleep(interval_sec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
