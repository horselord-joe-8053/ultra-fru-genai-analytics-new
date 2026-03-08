#!/usr/bin/env python3
"""
Local deploy: PostgreSQL + DB setup + kube/nonkube scopes (mirrors cloud deploy flow).

Usage:
  python orchestrator.py deploy --provider local --scope kube
  python tools/local/deploy.py --scope kube
  python tools/local/deploy.py --scope nonkube
  python tools/local/deploy.py --scope all [--skip-spark]

Scopes:
  kube:    Docker Desktop Kubernetes (API + CronJob in k8s)
  nonkube: Docker Compose API + scheduler_local (Spark via docker run)
  all:     nonkube first, then kube (like AWS/GCP)

Requires: .env, Docker Desktop with Kubernetes enabled for scope=kube.
"""
import argparse
import os
import subprocess
import sys
import time

# Allow running as script without PYTHONPATH (e.g. python tools/local/deploy.py)
_here = os.path.abspath(os.path.dirname(__file__))
_project_root = os.path.abspath(os.path.join(_here, "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.local.scope_shared.local_deploy_config import get_ports_for_scope

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE_LOCAL = "tools/local/docker/docker-compose.local.yml"
COMPOSE_NONKUBE = "tools/local/docker/docker-compose.nonkube.yml"
COMPOSE_PROJECT = "fru_local"


def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> int:
    e = env or os.environ.copy()
    e.setdefault("PYTHONPATH", PROJECT_ROOT)
    r = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, env=e)
    return r.returncode


def _docker_compose(*args: str, files: tuple[str, ...] | None = None) -> int:
    f = files or (COMPOSE_LOCAL,)
    return _run(
        ["docker", "compose"] + [x for ff in f for x in ("-f", ff)] + ["-p", COMPOSE_PROJECT] + list(args),
        cwd=PROJECT_ROOT,
    )


def _wait_for_postgres(timeout_sec: int = 60) -> bool:
    pw = os.environ.get("PGPASSWORD", "")
    if not pw:
        logger.error("PGPASSWORD required")
        return False
    start = time.time()
    while time.time() - start < timeout_sec:
        r = subprocess.run(
            [
                "docker", "exec", "fru-postgres",
                "pg_isready", "-U", "postgres", "-d", os.environ.get("PGDATABASE", "fru_db"),
            ],
            capture_output=True,
        )
        if r.returncode == 0:
            logger.success("PostgreSQL ready")
            return True
        time.sleep(2)
    logger.error("PostgreSQL not ready within timeout")
    return False


def _build_images(skip_spark: bool, force_rebuild: bool = False) -> int:
    """Build fru-api:local and fru-spark:local."""
    build_args = ["docker", "build", "-q", "-f", "core_app/Dockerfile", "-t", "fru-api:local"]
    if force_rebuild:
        build_args.insert(2, "--no-cache")
    build_args.extend(["core_app"])
    logger.step("Building API image (fru-api:local)" + (" (--no-cache)" if force_rebuild else "") + "...")
    r = subprocess.run(build_args, cwd=PROJECT_ROOT)
    if r.returncode != 0:
        logger.error("API image build failed")
        return 1

    if not skip_spark:
        spark_args = [
            "docker", "build", "-q",
            "--platform", "linux/amd64",
            "-f", "core_app/analytics/docker/Dockerfile",
            "-t", "fru-spark:local",
            "core_app",
        ]
        if force_rebuild:
            spark_args.insert(2, "--no-cache")
        logger.step("Building Spark image (fru-spark:local)" + (" (--no-cache)" if force_rebuild else "") + "...")
        r = subprocess.run(spark_args, cwd=PROJECT_ROOT)
        if r.returncode != 0:
            logger.error("Spark image build failed")
            return 1
    return 0


def _run_bootstrap_spark() -> int:
    """One-off Spark bootstrap (for nonkube; kube uses Job)."""
    pw = os.environ.get("PGPASSWORD", "")
    if not pw:
        logger.error("PGPASSWORD required")
        return 1
    r = subprocess.run(
        [
            "docker", "run", "--rm", "--user", "root",
            "--network", f"{COMPOSE_PROJECT}_default",
            "-e", "PGHOST=postgres", "-e", "PGPORT=5432", "-e", "PGUSER=postgres",
            "-e", f"PGPASSWORD={pw}", "-e", f"PGDATABASE={os.environ.get('PGDATABASE', 'fru_db')}",
            "-e", "DELTA_TABLE_PATH=file:///tmp/delta/fru_sales", "-v", "fru_delta:/tmp/delta",
            "fru-spark:local",
            "/opt/spark/bin/spark-submit",
            "--packages", "io.delta:delta-spark_2.12:3.1.0",
            "--conf", "spark.driver.extraJavaOptions=-Duser.home=/tmp",
            "--conf", "spark.executor.extraJavaOptions=-Duser.home=/tmp",
            "/opt/fru/jobs/run_analytics.py",
        ],
        cwd=PROJECT_ROOT,
    )
    return 0 if r.returncode == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="all",
                    help="Deploy scope (default: all)")
    ap.add_argument("--skip-spark", action="store_true", help="Skip Spark build/bootstrap")
    ap.add_argument("--force-refresh-data", action="store_true",
                    help="Force reload DB (schema, raw, embeddings) and re-run kube bootstrap; default is idempotent (skip if already loaded)")
    ap.add_argument("--force-rebuild", action="store_true",
                    help="Force rebuild Docker images (--no-cache); default uses cache")
    args = ap.parse_args()

    logger.step(
        f"Local deploy: scope={args.scope}"
        + (" (force-refresh-data)" if args.force_refresh_data else " (idempotent)")
        + (" (force-rebuild)" if args.force_rebuild else "")
    )

    # 1. Start PostgreSQL
    logger.info("Starting PostgreSQL...")
    if _docker_compose("up", "-d", files=(COMPOSE_LOCAL,)) != 0:
        logger.error("Failed to start PostgreSQL")
        return 1

    if not _wait_for_postgres():
        return 1

    # 2. DB setup
    logger.step("Running DB setup (schema, fru_sales_raw, embeddings)...")
    os.environ["PGHOST"] = "localhost"
    csv_path = os.path.join(PROJECT_ROOT, "core_app", "data", "raw", "fridge_sales_with_rating.csv")
    if not os.path.exists(csv_path):
        logger.error(f"CSV not found: {csv_path}")
        return 1

    setup_db_cmd = [sys.executable, "tools/gcp/scope_shared/deploy/setup_database.py", "--env-only"]
    if args.force_refresh_data:
        setup_db_cmd.append("--force-refresh-data")
    if _run(setup_db_cmd) != 0:
        logger.error("DB setup failed")
        return 1

    # 3. Build images
    if _build_images(args.skip_spark, force_rebuild=args.force_rebuild) != 0:
        return 1

    scopes = ["nonkube", "kube"] if args.scope == "all" else [args.scope]

    for scope in scopes:
        if scope == "nonkube":
            logger.step("Deploying local nonkube (API container + Spark bootstrap)")
            from tools.local.nonkube.deploy_nonkube import run_deploy_nonkube
            if run_deploy_nonkube(skip_spark=args.skip_spark) != 0:
                return 1
        elif scope == "kube":
            logger.step("Deploying local kube (Docker Desktop Kubernetes)")
            if _run([sys.executable, "tools/local/kube/kube_apply.py", "--phase", "bootstrap"]) != 0:
                return 1
            if not args.skip_spark:
                if _run([sys.executable, "tools/local/kube/kube_apply.py", "--phase", "schedule"]) != 0:
                    return 1

    logger.success("Local deploy complete")
    if "nonkube" in scopes:
        p = get_ports_for_scope("nonkube")
        logger.info(f"Nonkube API: http://localhost:{p['api_port']}  Frontend: http://localhost:{p['frontend_port']}")
    if "kube" in scopes:
        p = get_ports_for_scope("kube")
        logger.info(f"Kube API: http://localhost:{p['api_port']} (NodePort)  Frontend: http://localhost:{p['frontend_port']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
