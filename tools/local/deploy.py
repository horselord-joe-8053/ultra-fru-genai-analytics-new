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

from tools.cloud_shared.env import load_dotenv, require
from tools.cloud_shared.logging import logger
from tools.cloud_shared.docker.build_common import run_docker_with_progress
from tools.cloud_shared.docker.build_context_hash import (
    LOCAL_DEFAULT_REGION,
    compute_build_context_hash,
    store_build_hash,
)
from tools.cloud_shared.docker.build_skip_decision import decide_build_skip
from tools.local.scope_shared.local_deploy_config import get_memo_dir, get_ports_for_scope

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE_LOCAL = "tools/local/docker/docker-compose.local.yml"
COMPOSE_NONKUBE = "tools/local/docker/docker-compose.nonkube.yml"
COMPOSE_PROJECT = "fru_local"
MEMO_DIR = get_memo_dir()
BUILD_METADATA_PREFIX = f"build-metadata/{LOCAL_DEFAULT_REGION}"


def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> int:
    e = env or os.environ.copy()
    e.setdefault("PYTHONPATH", PROJECT_ROOT)
    r = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, env=e)
    return r.returncode


def _docker_compose(*args: str, files: tuple[str, ...] | None = None) -> int:
    """Wrapper around docker compose with logging and timing."""
    f = files or (COMPOSE_LOCAL,)
    cmd = ["docker", "compose"] + [x for ff in f for x in ("-f", ff)] + ["-p", COMPOSE_PROJECT] + list(args)
    logger.info(f"[local-deploy] Running docker compose: {' '.join(cmd)}")
    start = time.time()
    rc = _run(cmd, cwd=PROJECT_ROOT)
    elapsed = time.time() - start
    if rc == 0:
        logger.info(f"[local-deploy] docker compose finished OK in {elapsed:.1f}s")
    else:
        logger.error(f"[local-deploy] docker compose failed (exit {rc}) after {elapsed:.1f}s")
    return rc


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


def _build_images(skip_spark: bool, no_cache: bool = False) -> int:
    """Build fru-api:local and fru-spark:local. Uses --progress=plain for streaming log output."""
    total = 2 if not skip_spark else 1
    app_cmd = ["docker", "build", "--progress=plain", "-f", "core_app/Dockerfile", "-t", "fru-api:local"]
    if no_cache:
        app_cmd.insert(2, "--no-cache")
    app_cmd.append("core_app")
    try:
        run_docker_with_progress(
            app_cmd, "Building API image (fru-api:local)", 1, total, cwd=PROJECT_ROOT
        )
    except subprocess.CalledProcessError:
        logger.error("API image build failed")
        return 1

    if not skip_spark:
        spark_cmd = [
            "docker", "build", "--progress=plain",
            "--platform", "linux/amd64",
            "-f", "core_app/analytics/docker/Dockerfile",
            "-t", "fru-spark:local",
            "core_app",
        ]
        if no_cache:
            spark_cmd.insert(2, "--no-cache")
        try:
            run_docker_with_progress(
                spark_cmd, "Building Spark image (fru-spark:local)", 2, total, cwd=PROJECT_ROOT
            )
        except subprocess.CalledProcessError:
            logger.error("Spark image build failed")
            return 1
    return 0


def _run_bootstrap_spark() -> int:
    """One-off Spark bootstrap (for nonkube; kube uses Job)."""
    pw = os.environ.get("PGPASSWORD", "")
    if not pw:
        logger.error("PGPASSWORD required")
        return 1
    delta_pkg = require("DELTA_LAKE_PACKAGE")
    storage_pkg = require("DELTA_STORAGE_PACKAGE")
    packages = f"{delta_pkg},{storage_pkg}"
    r = subprocess.run(
        [
            "docker", "run", "--rm", "--user", "root",
            "--network", f"{COMPOSE_PROJECT}_default",
            "-e", "PGHOST=postgres", "-e", "PGPORT=5432", "-e", "PGUSER=postgres",
            "-e", f"PGPASSWORD={pw}", "-e", f"PGDATABASE={os.environ.get('PGDATABASE', 'fru_db')}",
            "-e", "DELTA_TABLE_PATH=file:///tmp/delta/fru_sales", "-v", "fru_delta:/tmp/delta",
            "fru-spark:local",
            "/opt/spark/bin/spark-submit",
            "--packages", packages,
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
    ap.add_argument("--force-build", action="store_true",
                    help="Bypass content-hash skip; always build images")
    ap.add_argument("--no-cache", action="store_true",
                    help="Build images with Docker --no-cache (cache-free build)")
    args = ap.parse_args()

    logger.step(
        f"Local deploy: scope={args.scope}"
        + (" (force-refresh-data)" if args.force_refresh_data else " (idempotent)")
        + (" (force-build)" if args.force_build else "")
        + (" (no-cache)" if args.no_cache else "")
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

    # 3. Build images (content-hash skip when hashes match stored in memo/)
    app_key = f"{BUILD_METADATA_PREFIX}/app-build-hash.json"
    spark_key = f"{BUILD_METADATA_PREFIX}/spark-build-hash.json"
    skip_result = decide_build_skip(
        force_build=args.force_build,
        storage_bucket=MEMO_DIR,
        app_key=app_key,
        spark_key=spark_key,
        provider="local",
        skip_spark=args.skip_spark,
    )
    if skip_result.skip:
        logger.step(f"Will skip building images because {skip_result.skip_reason}")
        logger.info(f"App hash {skip_result.app_hash[:8]}... matches. Use --force-build to rebuild.")
    else:
        if args.force_build:
            logger.step("Will start building images because --force-build was set.")
        else:
            logger.step("Will start building images because content hash does not match stored or first deploy.")
        if args.no_cache:
            logger.info("Building with --no-cache (cache-free).")
        if _build_images(args.skip_spark, no_cache=args.no_cache) != 0:
            return 1
        store_build_hash(MEMO_DIR, app_key, "local", skip_result.app_hash, "latest")
        if not args.skip_spark and skip_result.spark_hash:
            store_build_hash(MEMO_DIR, spark_key, "local", skip_result.spark_hash, "latest")

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
