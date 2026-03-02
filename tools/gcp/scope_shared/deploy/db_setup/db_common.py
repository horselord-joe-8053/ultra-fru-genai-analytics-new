"""
Shared DB utilities for db-setup Cloud Run Job scripts.

Used by run_schema_and_load.py and setup_database.py (host).
"""
import os

from tools.cloud_shared.deploy.setup_database_utils import FORCE_DROP_TABLES


def get_db_config(
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    dbname: str | None = None,
) -> dict:
    """Read DB config from env, with optional overrides. Raises if PGHOST or PGPASSWORD missing (when not overridden)."""
    h = host if host is not None else os.getenv("PGHOST", "").strip()
    p = port if port is not None else int(os.getenv("PGPORT", "5432"))
    u = user if user is not None else (os.getenv("PGUSER", "postgres").strip() or "postgres")
    pw = password if password is not None else os.getenv("PGPASSWORD", "").strip()
    db = dbname if dbname is not None else (os.getenv("PGDATABASE", "fru_db").strip() or "fru_db")
    if not h or not pw:
        raise RuntimeError("PGHOST and PGPASSWORD required")
    return {"host": h, "port": p, "user": u, "password": pw, "dbname": db}


def connect_db(config: dict):
    """Connect to PostgreSQL. Returns psycopg2 connection."""
    import psycopg2
    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        dbname=config["dbname"],
        connect_timeout=10,
    )


def apply_schema(conn, schema_path: str, force: bool = False) -> None:
    """Apply schema from schema_path. Drop FORCE_DROP_TABLES when force=True."""
    from tools.cloud_shared.logging.logger import info, success, error, step
    from tools.cloud_shared.sql.parse_sql_statements import parse_sql_statements

    step(f"Reading schema from {schema_path}")
    with open(schema_path) as f:
        statements = parse_sql_statements(f.read())
    info(f"Parsed {len(statements)} SQL statements")

    with conn.cursor() as cur:
        if force:
            step("Force mode: dropping tables")
            for table in FORCE_DROP_TABLES:
                try:
                    cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                    conn.commit()
                    info(f"Dropped table {table}")
                except Exception as e:
                    conn.rollback()
                    error(f"Drop {table}: {e}")
        step("Applying schema statements...")
        for i, stmt in enumerate(statements):
            try:
                cur.execute(stmt)
                conn.commit()
                info(f"Executed statement {i + 1}/{len(statements)}")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e).lower():
                    info(f"Statement {i + 1} skipped (already exists)")
                else:
                    error(f"Statement {i + 1} failed: {e}")
                    raise
    success("Schema applied successfully")
