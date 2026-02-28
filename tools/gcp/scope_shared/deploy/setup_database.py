#!/usr/bin/env python3
"""
GCP Cloud SQL database setup: run schema (pgvector, batch_analytics, fru_sales_embeddings).

For private-IP-only Cloud SQL, run from a machine with VPC access (e.g. GCE VM in same VPC):
  cloud-sql-proxy --private-ip fru-proj-1:us-central1:fru-dev-sql &
  PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres PGPASSWORD=... PGDATABASE=fru_db python tools/gcp/scope_shared/deploy/setup_database.py

For public IP (if enabled):
  python tools/gcp/scope_shared/deploy/setup_database.py --env dev --region us-central1 --use-proxy
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SCHEMA_FILE = os.path.join(REPO_ROOT, "core_app", "sql", "schema_pgvector.sql")
PARSE_SQL = os.path.join(REPO_ROOT, "tools", "cloud_shared", "sql", "parse_sql_statements.py")


def get_durable_outputs(env: str, region: str) -> dict:
    """Get Cloud SQL connection info from durable stack."""
    from tools.gcp.scope_shared.core.backend import backend_config
    from tools.gcp.scope_shared.core.terra_runner import get_terra_env

    stack_dir = os.path.join(REPO_ROOT, "infra_terraform/live_deploy/gcp/scope_shared/durable")
    cfg = backend_config(stack_dir, env, region, cloud="gcp")
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    subprocess.run([exe] + args, cwd=stack_dir, env=get_terra_env(region), check=True, capture_output=True)
    out_raw = subprocess.check_output([exe, "output", "-json"], cwd=stack_dir, text=True, env=get_terra_env(region))
    out = json.loads(out_raw)
    conn_name = out.get("cloud_sql_connection_name", {}).get("value", "")
    private_ip = out.get("cloud_sql_private_ip", {}).get("value", "")
    db_name = out.get("cloud_sql_database_name", {}).get("value", "fru_db")
    return {"connection_name": conn_name, "private_ip": private_ip, "db_name": db_name}


def run_schema(host: str, port: int, user: str, password: str, dbname: str) -> None:
    """Execute schema SQL via psycopg2."""
    import psycopg2

    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")
    if not os.path.exists(PARSE_SQL):
        raise FileNotFoundError(f"parse_sql_statements.py not found: {PARSE_SQL}")

    result = subprocess.run(
        [sys.executable, PARSE_SQL, SCHEMA_FILE],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to parse schema: {result.stderr}")

    statements = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            for i, stmt in enumerate(statements):
                try:
                    cur.execute(stmt)
                    conn.commit()
                    logger.info(f"Executed statement {i + 1}/{len(statements)}")
                except Exception as e:
                    conn.rollback()
                    if "already exists" in str(e).lower():
                        logger.info(f"Statement {i + 1} skipped (already exists)")
                    else:
                        raise
        logger.success("Schema applied successfully")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Setup GCP Cloud SQL schema")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=os.getenv("GCP_REGION") or os.getenv("CLOUD_REGION", "us-central1"))
    ap.add_argument("--use-proxy", action="store_true",
        help="Start Cloud SQL Proxy and connect to localhost (requires cloud_sql_proxy in PATH)")
    args = ap.parse_args()

    host = os.getenv("PGHOST", "").strip()
    port = int(os.getenv("PGPORT", "5432"))
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "").strip()
    dbname = os.getenv("PGDATABASE", "fru_db")

    if args.use_proxy:
        outputs = get_durable_outputs(args.env, args.region)
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
        # Use default port 5432 for Postgres (proxy listens on localhost:5432)
        # Note: For private-IP-only instances, run this from a machine with VPC access (e.g. GCE VM)
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
            run_schema(host, port, user, password, dbname or outputs["db_name"])
        finally:
            proxy.terminate()
            proxy.wait(timeout=5)
    elif host and password:
        run_schema(host, port, user, password, dbname)
    else:
        logger.error("Set PGHOST, PGPASSWORD (and optionally PGUSER, PGDATABASE) or use --use-proxy")
        logger.info("For private IP: run 'cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432' first, then PGHOST=localhost")
        sys.exit(1)


if __name__ == "__main__":
    main()
