#!/usr/bin/env python3
"""
GCP Cloud SQL database setup: pgvector, schema, load_data.
Overlord for db setup; consistent with tools/aws/scope_shared/deploy/setup_database.py.

1. Usage
   python tools/gcp/scope_shared/deploy/setup_database.py --env dev --region us-central1
   python tools/gcp/scope_shared/deploy/setup_database.py --env dev --force-refresh-data

2. Requirements
   PGPASSWORD in .env; durable stack applied.

3. Deploy behavior (main flow)
   tools/gcp/deploy.py invokes with --env and --region only. No PGHOST → Cloud Run Job
   container runs schema + load_data inside GCP; host verifies record count from logs.
   The ETL (schema + embeddings load) runs entirely in the container, not on the host.

4. Manual-only options (not used by deploy; for local/CI when you have direct TCP to DB)

   4.1 --use-proxy
       Cloud SQL Proxy locally; connect to localhost:5432. Use from laptop when you want
       schema + load_data (Cloud Run Job does both).
       Prerequisite: public IP on Cloud SQL (durable stack is private-IP only).
       Workflow:
         (1) gcloud sql instances patch INSTANCE_NAME --assign-ip --project=PROJECT
             (INSTANCE_NAME = last part of cloud_sql_connection_name "project:region:instance")
         (2) python setup_database.py --env dev --region us-central1 --use-proxy
         (3) gcloud sql instances patch INSTANCE_NAME --no-assign-ip --project=PROJECT
       Install: gcloud components install cloud-sql-proxy

   4.2 --env-only
       Use PGHOST, PGPASSWORD from env. For machines in same VPC as Cloud SQL (GCP VM,
       Cloud Shell, container). Set PGHOST to private IP (durable outputs), PGPASSWORD.

   4.3 PGHOST=... (no flag)
       Direct TCP when machine can reach private IP. Same as 4.2; inferred when both
       PGHOST and PGPASSWORD are set.

   4.4 --use-cloud-job
       Explicitly use Cloud Run Job (default when no PGHOST). Schema + load_data.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.cloud_shared.deploy.setup_database_utils import get_csv_path, get_schema_file_path
from tools.gcp.scope_shared.deploy.db_setup.db_common import (
    apply_schema,
    connect_db,
    get_db_config,
)
from tools.gcp.scope_shared.deploy.db_setup.load import load_raw_from_csv, load_embeddings

load_dotenv()


def get_durable_outputs(env: str, region: str) -> dict:
    """Get Cloud SQL connection info from durable stack. Uses retry for tofu init."""
    from tools.gcp.scope_shared.deploy.db_setup.config import get_tofu_output_json

    out = get_tofu_output_json("infra_terraform/live_deploy/gcp/scope_shared/durable", env, region, description="durable")
    conn_name = out.get("cloud_sql_connection_name", {}).get("value", "")
    private_ip = out.get("cloud_sql_private_ip", {}).get("value", "")
    db_name = out.get("cloud_sql_database_name", {}).get("value", "fru_db")
    return {"connection_name": conn_name, "private_ip": private_ip, "db_name": db_name}


# -----------------------------------------------------------------------------
# Local / manual ETL path (_do_schema_and_load)
# -----------------------------------------------------------------------------
# NOT part of the main deploy flow. The main deploy flow uses a Cloud Run Job
# container (run_schema_and_load.py) that runs schema + load inside GCP.
#
# _do_schema_and_load is for manual or CI deployment when you have direct TCP
# to Cloud SQL: --env-only (VPC VM/Cloud Shell), --use-proxy (laptop with
# Cloud SQL Proxy), or PGHOST set (machine in same VPC).
# -----------------------------------------------------------------------------


def _do_schema_and_load(
    host: str, port: int, user: str, password: str, dbname: str, force: bool = False
) -> None:
    """Apply schema, load fru_sales_raw from CSV, then load embeddings. For manual/local/CI when direct TCP to DB."""
    config = get_db_config(host=host, port=port, user=user, password=password, dbname=dbname)
    conn = connect_db(config)
    try:
        apply_schema(conn, schema_path=get_schema_file_path(), force=force)
        load_raw_from_csv(conn, csv_path=get_csv_path(), force=force)
        load_embeddings(conn, csv_path=None, config=config, force=force)
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Setup GCP Cloud SQL (pgvector, schema, data)")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=os.getenv("CLOUD_REGION", "us-central1"))
    ap.add_argument("--force-refresh-data", action="store_true", help="Drop tables and reload (match AWS)")
    ap.add_argument("--use-proxy", action="store_true",
        help="Start Cloud SQL Proxy locally; needs public IP enabled on Cloud SQL (see module docstring)")
    ap.add_argument("--env-only", action="store_true",
        help="Use PGHOST, PGPASSWORD from env; for VPC machines (VM, Cloud Shell, container)")
    ap.add_argument("--use-cloud-job", action="store_true",
        help="Run schema + load_data via Cloud Run Job (default when no PGHOST)")
    args = ap.parse_args()

    from tools.gcp.scope_shared.core.backend import resolve_region
    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    host = os.getenv("PGHOST", "").strip()
    port = int(os.getenv("PGPORT", "5432"))
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "").strip()
    dbname = os.getenv("PGDATABASE", "fru_db")

    # localhost/127.0.0.1 from .env cannot reach private-IP Cloud SQL; clear to force Cloud Run Job.
    # Exception: --env-only trusts caller (e.g. local deploy with PGHOST=localhost).
    if not args.env_only and host in ("localhost", "127.0.0.1"):
        host = ""

    logger.step("Setting up database (pgvector, schema, data)")

    # --env-only: use PGHOST, PGPASSWORD from env (VM, Cloud Shell, container, or local Postgres)
    if args.env_only:
        if not host or not password:
            logger.error("--env-only requires PGHOST and PGPASSWORD")
            sys.exit(1)
        _do_schema_and_load(host, port, user, password, dbname or "fru_db", force=args.force_refresh_data)
        logger.success("Database setup completed")
        return

    # --use-cloud-job or no direct path: run via Cloud Run Job + verify (private-IP Cloud SQL)
    if args.use_cloud_job or (not host and not args.use_proxy):
        from tools.gcp.scope_shared.deploy.db_setup.cloud_job import run_and_verify, run_verify_only
        try:
            if not run_and_verify(args.env, region, force=args.force_refresh_data):
                sys.exit(1)
        except Exception as e:
            logger.warning(f"Database setup failed: {e}")
            # Smart DB loading strategy: do not fail-fast. Run verify-only to see if the DB
            # was already initialized (e.g. previous run succeeded, or this run timed out
            # after load completed). Only fail deploy if verify-only shows wrong/missing data.
            logger.info("Checking if DB is already initialized (verify-only)...")
            if run_verify_only(args.env, region):
                logger.success("Database already initialized; continuing")
                return
            raise
        logger.success("Database setup completed")
        return

    # --use-proxy: start Cloud SQL Proxy locally; requires public IP on Cloud SQL (see docstring)
    if args.use_proxy:
        outputs = get_durable_outputs(args.env, region)
        conn_name = outputs["connection_name"]
        if not conn_name:
            logger.error("cloud_sql_connection_name not in durable outputs")
            sys.exit(1)
        project = os.getenv("GCP_PROJECT_ID", "").strip()
        if not project:
            logger.error("GCP_PROJECT_ID required for proxy")
            sys.exit(1)
        logger.step("Starting Cloud SQL Proxy...")
        proxy_cmd = shutil.which("cloud-sql-proxy") or shutil.which("cloud_sql_proxy")
        if not proxy_cmd:
            logger.error("cloud-sql-proxy not found. Install: gcloud components install cloud-sql-proxy")
            sys.exit(1)
        proxy = subprocess.Popen(
            [proxy_cmd, conn_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            for _ in range(12):
                time.sleep(1)
                if proxy.poll() is not None:
                    err = proxy.stderr.read().decode() if proxy.stderr else ""
                    raise RuntimeError(f"Cloud SQL Proxy exited: {err}")
            host = "127.0.0.1"
            port = 5432
            if not password:
                logger.error("PGPASSWORD required")
                sys.exit(1)
            _do_schema_and_load(host, port, user, password, dbname or outputs["db_name"], force=args.force_refresh_data)
        finally:
            proxy.terminate()
            proxy.wait(timeout=5)
        logger.success("Database setup completed")
        return

    # Direct PGHOST: machine can reach private IP (VM, container in VPC)
    if host and password:
        _do_schema_and_load(host, port, user, password, dbname, force=args.force_refresh_data)
        logger.success("Database setup completed")
        return

    # No path: default to cloud job + verify
    logger.info("No PGHOST set; using Cloud Run Job for private-IP Cloud SQL")
    from tools.gcp.scope_shared.deploy.db_setup.cloud_job import run_and_verify, run_verify_only
    try:
        if not run_and_verify(args.env, region, force=args.force_refresh_data):
            sys.exit(1)
    except Exception as e:
        logger.warning(f"Database setup failed: {e}")
        # Smart DB loading strategy: do not fail-fast; run verify-only (see cloud_job.run_verify_only).
        logger.info("Checking if DB is already initialized (verify-only)...")
        if run_verify_only(args.env, region):
            logger.success("Database already initialized; continuing")
            return
        raise
    logger.success("Database setup completed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
