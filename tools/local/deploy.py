#!/usr/bin/env python3
"""
Local deploy: PostgreSQL (Docker) + DB setup + Spark job (Docker).

Usage:
  python orchestrator.py deploy --provider local
  python tools/local/deploy.py [--skip-spark]

Requires: .env with PGHOST=localhost, PGPASSWORD, PGDATABASE, OPENAI_API_KEY, etc.
After deploy: run API (PORT=5001) and frontend (npm run dev) manually.
"""
import argparse
import os
import subprocess
import sys
import time

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE_FILE = "docker-compose.local.yml"
COMPOSE_PROJECT = "fru_local"


def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> int:
    e = env or os.environ.copy()
    e.setdefault("PYTHONPATH", PROJECT_ROOT)
    r = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, env=e)
    return r.returncode


def _docker_compose(*args: str) -> int:
    return _run(
        ["docker", "compose", "-f", COMPOSE_FILE, "-p", COMPOSE_PROJECT] + list(args),
        cwd=PROJECT_ROOT,
    )


def _wait_for_postgres(timeout_sec: int = 60) -> bool:
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "fru_db")
    pw = os.environ.get("PGPASSWORD", "")
    if not pw:
        logger.error("PGPASSWORD required")
        return False
    start = time.time()
    while time.time() - start < timeout_sec:
        r = subprocess.run(
            [
                "docker", "exec", "fru-postgres",
                "pg_isready", "-U", "postgres", "-d", db,
            ],
            capture_output=True,
        )
        if r.returncode == 0:
            logger.success("PostgreSQL ready")
            return True
        time.sleep(2)
    logger.error("PostgreSQL not ready within timeout")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-spark", action="store_true", help="Skip Spark build and job (e.g. when disk full)")
    args = ap.parse_args()

    logger.step("Local deploy: PostgreSQL + DB setup + Spark")

    # 1. Start PostgreSQL
    logger.info("Starting PostgreSQL (Docker)...")
    if _docker_compose("up", "-d") != 0:
        logger.error("Failed to start PostgreSQL")
        return 1

    if not _wait_for_postgres():
        return 1

    # 2. DB setup (schema + load_raw + load_embeddings)
    logger.step("Running DB setup (schema, fru_sales_raw, embeddings)...")
    os.environ["PGHOST"] = "localhost"
    csv_path = os.path.join(PROJECT_ROOT, "core_app", "data", "raw", "fridge_sales_with_rating.csv")
    if not os.path.exists(csv_path):
        logger.error(f"CSV not found: {csv_path}")
        return 1

    r = _run([
        sys.executable, "tools/gcp/scope_shared/deploy/setup_database.py",
        "--env-only", "--force-refresh-data",
    ])
    if r != 0:
        logger.error("DB setup failed")
        return 1

    # 3. Build Spark image and run job (optional; skip if --skip-spark or disk full)
    if not args.skip_spark:
        logger.step("Building Spark image...")
        r = subprocess.run(
            [
                "docker", "build", "-q",
                "-f", "core_app/analytics/docker/Dockerfile",
                "-t", "fru-spark:local",
                "core_app",
            ],
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            logger.warning("Spark image build failed (e.g. disk full); continuing without Spark. Use --skip-spark to skip.")
        else:
            logger.step("Running Spark analytics job...")
            pw = os.environ.get("PGPASSWORD", "")
            if pw:
                spark_cmd = [
                    "docker", "run", "--rm",
                    "--network", f"{COMPOSE_PROJECT}_default",
                    "-e", "PGHOST=postgres",
                    "-e", "PGPORT=5432",
                    "-e", "PGUSER=postgres",
                    "-e", f"PGPASSWORD={pw}",
                    "-e", f"PGDATABASE={os.environ.get('PGDATABASE', 'fru_db')}",
                    "-e", "DELTA_TABLE_PATH=file:///tmp/delta/fru_sales",
                    "-v", "fru_delta:/tmp/delta",
                    "fru-spark:local",
                    "/opt/spark/bin/spark-submit",
                    "--packages", "io.delta:delta-spark_2.12:3.1.0",
                    "--conf", "spark.driver.extraJavaOptions=-Duser.home=/tmp",
                    "--conf", "spark.executor.extraJavaOptions=-Duser.home=/tmp",
                    "/opt/fru/jobs/run_analytics.py",
                ]
                r = subprocess.run(spark_cmd, cwd=PROJECT_ROOT)
                if r.returncode != 0:
                    logger.warning("Spark job failed; /analytics may be empty")
            else:
                logger.warning("PGPASSWORD not set; skipping Spark job")
    else:
        logger.info("Skipping Spark (--skip-spark)")

    logger.success("Local deploy complete")
    logger.info("Next (from project root):")
    logger.info("  API:      PORT=5001 PYTHONPATH=core_app python -m backend.api.app")
    logger.info("  Frontend: cd core_app/frontend && npm run dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
