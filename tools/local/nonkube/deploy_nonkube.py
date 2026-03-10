"""
Local nonkube deploy: API in Docker container + Spark via scheduler (mirrors Cloud Run + Cloud Scheduler).

Requires: postgres already running (from deploy.py base), fru-api:local and fru-spark:local built.
"""
import os
import subprocess
import sys

from tools.cloud_shared.analytics_schedule import get_required_analytics_scheduler_interval_seconds
from tools.cloud_shared.env import load_dotenv, require
from tools.cloud_shared.logging import logger

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COMPOSE_LOCAL = "tools/local/docker/docker-compose.local.yml"
COMPOSE_NONKUBE = "tools/local/docker/docker-compose.nonkube.yml"
COMPOSE_PROJECT = "fru_local"


def _run(cmd: list, env: dict | None = None) -> int:
    e = env or os.environ.copy()
    e.setdefault("PYTHONPATH", PROJECT_ROOT)
    r = subprocess.run(cmd, cwd=PROJECT_ROOT, env=e)
    return r.returncode


def _docker_compose(*args: str) -> int:
    return _run(
        [
            "docker", "compose",
            "-f", COMPOSE_LOCAL,
            "-f", COMPOSE_NONKUBE,
            "-p", COMPOSE_PROJECT,
        ] + list(args),
    )


def run_deploy_nonkube(skip_spark: bool = False) -> int:
    """Deploy local nonkube: API container + bootstrap Spark + optional scheduler."""
    get_required_analytics_scheduler_interval_seconds()

    logger.step("Local nonkube: API container + Spark bootstrap")

    # Ensure postgres + api are up
    if _docker_compose("up", "-d") != 0:
        logger.error("Failed to start postgres + api")
        return 1

    if not skip_spark:
        logger.step("Running Spark bootstrap...")
        pw = os.environ.get("PGPASSWORD", "")
        if not pw:
            logger.error("PGPASSWORD required")
            return 1
        delta_pkg = require("DELTA_LAKE_PACKAGE")
        storage_pkg = require("DELTA_STORAGE_PACKAGE")
        packages = f"{delta_pkg},{storage_pkg}"
        spark_cmd = [
            "docker", "run", "--rm",
            "--user", "root",
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
            "--packages", packages,
            "--conf", "spark.driver.extraJavaOptions=-Duser.home=/tmp",
            "--conf", "spark.executor.extraJavaOptions=-Duser.home=/tmp",
            "/opt/fru/jobs/run_analytics.py",
        ]
        if _run(spark_cmd) != 0:
            logger.error("Spark bootstrap failed")
            return 1

    logger.success("Local nonkube deploy complete")
    logger.info("API: http://localhost:5001")
    logger.info("Frontend: http://localhost:5001 (served by API)")
    return 0


if __name__ == "__main__":
    sys.exit(run_deploy_nonkube(skip_spark=os.environ.get("SKIP_SPARK", "").lower() in ("true", "1", "yes")))
