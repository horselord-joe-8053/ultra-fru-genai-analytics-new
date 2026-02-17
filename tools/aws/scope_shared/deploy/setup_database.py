#!/usr/bin/env python3
"""
Database setup: ensure pgvector, init schema, load data.
Python equivalent of legacy module_infra_db/aws/setup-database.sh.

Usage:
  python tools/aws/scope_shared/deploy/setup_database.py --env dev
  python tools/aws/scope_shared/deploy/setup_database.py --env dev --force-refresh-data

Requires: PGPASSWORD in .env; durable stack applied.
"""
import argparse
import os
import subprocess
import sys

import json
import subprocess

from tools.cloud_shared.env import load_dotenv, require
from tools.aws.scope_shared.core.backend import backend_config, resolve_region
from tools.aws.scope_shared.core.terra_runner import get_terra_env
from tools.cloud_shared.retry import run_with_retry
from tools.cloud_shared.logging import logger

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SCHEMA_FILE = os.path.join(REPO_ROOT, "core_app", "sql", "schema_pgvector.sql")
PARSE_SQL = os.path.join(REPO_ROOT, "tools", "common", "sql", "parse_sql_statements.py")
ETL_SCRIPT = os.path.join(REPO_ROOT, "core_app", "backend", "etl", "load_openai_embeddings_to_pgvector_rds_api.py")


def get_durable_outputs(env: str, region: str | None = None) -> dict:
    """Get Aurora-related outputs from durable stack."""
    stack_dir = "infra_terraform/live_deploy/aws/scope_shared/durable"
    cfg = backend_config(stack_dir, env, region)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    run_with_retry([exe] + args, cwd=stack_dir, env=get_terra_env(region), description="tofu init for durable")
    out_raw = subprocess.check_output([exe, "output", "-json"], cwd=stack_dir, text=True, env=get_terra_env(region))
    out = json.loads(out_raw)
    cluster_arn = out.get("aurora_cluster_arn", {}).get("value")
    secret_arn = out.get("db_password_secret_arn", {}).get("value") or out.get("db_secret_arn", {}).get("value")
    db_name = out.get("aurora_database_name", {}).get("value", "fru_db")
    if not cluster_arn or not secret_arn:
        raise RuntimeError(
            "aurora_cluster_arn or db_password_secret_arn missing from durable outputs. "
            "Run deploy durable first and ensure Aurora was created (PGPASSWORD in .env)."
        )
    return {"cluster_arn": cluster_arn, "secret_arn": secret_arn, "db_name": db_name}


def ensure_pgvector(rds_client, cluster_arn: str, secret_arn: str, db_name: str) -> None:
    """Create pgvector extension via RDS Data API. Waits for readiness (legacy parity)."""
    logger.info("Ensuring pgvector extension...")
    try:
        rds_client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=db_name,
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
        )
        logger.success("pgvector extension created")
    except Exception as e:
        logger.warning(f"pgvector check had issues (may already exist): {e}")

    # Wait for pgvector to be usable (legacy: wait-for-pgvector-ready.sh)
    import time
    for attempt in range(6):
        try:
            rds_client.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=db_name,
                sql="SELECT 1 FROM (SELECT '[1,2,3]'::vector) t;",
            )
            logger.success("pgvector extension ready")
            return
        except Exception:
            pass
        if attempt < 5:
            logger.info(f"Waiting for pgvector readiness ({attempt + 1}/6)...")
            time.sleep(5)
    logger.warning("pgvector readiness check inconclusive; proceeding anyway")


def init_schema(rds_client, cluster_arn: str, secret_arn: str, db_name: str, force: bool = False) -> None:
    """Execute schema SQL statements via RDS Data API."""
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")
    if not os.path.exists(PARSE_SQL):
        raise FileNotFoundError(f"parse_sql_statements.py not found: {PARSE_SQL}")

    if force:
        for table in ["batch_analytics", "fru_sales_embeddings"]:
            try:
                rds_client.execute_statement(
                    resourceArn=cluster_arn,
                    secretArn=secret_arn,
                    database=db_name,
                    sql=f"DROP TABLE IF EXISTS {table} CASCADE;",
                )
            except Exception:
                pass

    result = subprocess.run(
        [sys.executable, PARSE_SQL, SCHEMA_FILE],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to parse schema: {result.stderr}")

    statements = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
    for i, stmt in enumerate(statements):
        try:
            rds_client.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=db_name,
                sql=stmt,
            )
            logger.info(f"Executed statement {i + 1}/{len(statements)}")
        except Exception as e:
            logger.warning(f"Statement {i + 1} failed (may be idempotent): {e}")

    # Schema verification (legacy parity)
    try:
        resp = rds_client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=db_name,
            sql="SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='fru_sales_embeddings' AND column_name='embedding');",
        )
        rec = resp.get("records", [[]])[0][0] if resp.get("records") else {}
        has_embedding = rec.get("booleanValue") is True
        if not has_embedding:
            raise RuntimeError("Schema verification failed: embedding column missing from fru_sales_embeddings")
        logger.success("Schema verification passed")
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning(f"Schema verification inconclusive: {e}")

    logger.success("Schema initialized")


def load_data(env: str, cluster_arn: str, secret_arn: str, db_name: str, force: bool = False) -> None:
    """Run ETL to load embeddings into Aurora."""
    if not os.path.exists(ETL_SCRIPT):
        logger.warning(f"ETL script not found: {ETL_SCRIPT}; skipping load_data")
        return

    csv_path = os.path.join(REPO_ROOT, "core_app", "data", "raw", "fridge_sales_with_rating.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    env_vars = os.environ.copy()
    env_vars["DB_CLUSTER_ARN"] = cluster_arn
    env_vars["DB_SECRET_ARN"] = secret_arn
    env_vars["PGDATABASE"] = db_name
    env_vars["FRU_CSV_PATH"] = csv_path
    env_vars.setdefault("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    # ETL imports backend.* - need core_app on PYTHONPATH
    core_app = os.path.join(REPO_ROOT, "core_app")
    env_vars["PYTHONPATH"] = core_app + (os.pathsep + env_vars.get("PYTHONPATH", "")) if env_vars.get("PYTHONPATH") else core_app

    # Idempotency: skip if data exists and not forcing (legacy parity)
    if not force:
        import boto3
        rds = boto3.client("rds-data", region_name=env_vars.get("CLOUD_REGION", env_vars.get("AWS_REGION", "us-east-1")))
        try:
            resp = rds.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=db_name,
                sql="SELECT COUNT(*) FROM fru_sales_embeddings;",
            )
            rows = 0
            if resp.get("records") and len(resp["records"]) > 0:
                rows = int(resp["records"][0][0].get("longValue", 0))
            if rows > 0:
                logger.info(f"Data already loaded ({rows} rows); skipping (use --force-refresh-data to reload)")
                return
        except Exception:
            pass  # Table may not exist yet

    logger.info("Loading data (embeddings)...")
    result = subprocess.run(
        [sys.executable, ETL_SCRIPT],
        env=env_vars,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError("Data loading failed")
    logger.success("Data loaded")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--force-refresh-data", action="store_true")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    os.environ["AWS_REGION"] = region

    logger.step("Setting up database (pgvector, schema, data)")

    try:
        import boto3
        rds = boto3.client("rds-data", region_name=region)

        outputs = get_durable_outputs(args.env, region)
        cluster_arn = outputs["cluster_arn"]
        secret_arn = outputs["secret_arn"]
        db_name = outputs["db_name"]

        ensure_pgvector(rds, cluster_arn, secret_arn, db_name)
        init_schema(rds, cluster_arn, secret_arn, db_name, force=args.force_refresh_data)
        load_data(args.env, cluster_arn, secret_arn, db_name, force=args.force_refresh_data)

        logger.success("Database setup completed")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
