#!/usr/bin/env python3
"""
Local teardown by scope (nonkube and kube do not affect each other; all removes everything).

- scope=kube:   k8s cleanup + hostPath /tmp/fru-delta. Postgres and nonkube API untouched.
- scope=nonkube: API container only (compose down with nonkube file), memo files removed. Postgres and kube untouched.
- scope=all:    shutdown_local (orchestrator), k8s cleanup, /tmp/fru-delta, full compose down, fru_delta volume,
                memo files. Local Docker images (fru-api:local, fru-spark:local) are removed only when
                --incl-dura or --incl-dura-all is used with scope=all (same condition as AWS/GCP).

Orchestrator runs shutdown_local before teardown when scope in (nonkube, all).
"""
import argparse
import os
import shutil
import subprocess
import sys

# Allow running as script without PYTHONPATH
_here = os.path.abspath(os.path.dirname(__file__))
_project_root = os.path.abspath(os.path.join(_here, "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.cloud_shared.logging import logger
from tools.cloud_shared.kube_pre_destroy import run_k8s_cleanup

PROJECT_ROOT = _project_root
COMPOSE_LOCAL = "tools/local/docker/docker-compose.local.yml"
COMPOSE_NONKUBE = "tools/local/docker/docker-compose.nonkube.yml"
COMPOSE_PROJECT = "fru_local"
MEMO_DIR = os.path.join(PROJECT_ROOT, "tools", "local", "memo")
HOSTPATH_FRU_DELTA = "/tmp/fru-delta"
LOCAL_IMAGES = ("fru-api:local", "fru-spark:local")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="all")
    ap.add_argument("--incl-dura", action="store_true", help="Include full teardown; when with scope=all, also remove local Docker images (aligns with AWS/GCP)")
    ap.add_argument("--incl-dura-all", action="store_true", help="Same as --incl-dura for local (aligns with AWS/GCP)")
    args = ap.parse_args()
    scopes = ["nonkube", "kube"] if args.scope == "all" else [args.scope]

    logger.step("Local teardown")

    if "kube" in scopes:
        logger.info("Pre-destroy kube (same sequence as AWS/GCP)...")
        run_k8s_cleanup()
        if os.path.exists(HOSTPATH_FRU_DELTA):
            shutil.rmtree(HOSTPATH_FRU_DELTA, ignore_errors=True)
            logger.info("Removed hostPath %s", HOSTPATH_FRU_DELTA)

    if args.scope in ("nonkube", "all"):
        for name in (".fru_local.pids", ".fru_local_api_port"):
            path = os.path.join(MEMO_DIR, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info("Removed memo %s", path)
                except OSError:
                    pass

    if "nonkube" in scopes and args.scope != "all":
        # Stop/remove only the nonkube API container (same project, nonkube file defines only api)
        logger.info("Stopping nonkube API container...")
        r = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_NONKUBE, "-p", COMPOSE_PROJECT, "down"],
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            logger.error("Nonkube compose down failed")
            return 1

    if args.scope == "all":
        # Full teardown: Postgres + any remaining compose resources, then volumes
        logger.info("Compose down (Postgres + project)...")
        r = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_LOCAL, "-f", COMPOSE_NONKUBE, "-p", COMPOSE_PROJECT, "down", "-v"],
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            logger.error("Compose down failed")
            return 1
        subprocess.run(["docker", "volume", "rm", "fru_delta"], capture_output=True)
        # Remove local Docker images only when --incl-dura or --incl-dura-all (same condition as AWS/GCP)
        if args.incl_dura or args.incl_dura_all:
            for img in LOCAL_IMAGES:
                subprocess.run(["docker", "rmi", img], capture_output=True)
                logger.info("Removed image %s (if present)", img)

    logger.success("Local teardown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
