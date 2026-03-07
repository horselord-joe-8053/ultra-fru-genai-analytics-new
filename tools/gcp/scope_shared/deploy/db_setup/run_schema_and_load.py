#!/usr/bin/env python3
"""
Cloud Run Job entrypoint: schema + load_data + record count.

Runs schema, load_data (idempotent: skip if data exists unless FRU_FORCE_REFRESH_DATA),
then outputs FRU_EMBEDDINGS_COUNT=N for verification scripts to parse from logs.

Reference data: core_app/data/raw/fridge_sales_with_rating.csv (201 rows).
Requires: PGHOST, PGPASSWORD, OPENAI_API_KEY, FRU_CSV_PATH (default /app/data/fridge_sales_with_rating.csv).
"""
import os
import sys

sys.path.insert(0, "/app")

from tools.cloud_shared.logging.logger import info, success, error, step

from db_common import apply_schema, connect_db, get_db_config
from load import load_raw_from_csv, load_embeddings


def _get_optional(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def main() -> None:
    step("Cloud Run Job started")
    verify_only = os.getenv("FRU_VERIFY_ONLY", "").lower() in ("1", "true", "yes")
    force = os.getenv("FRU_FORCE_REFRESH_DATA", "").lower() in ("1", "true", "yes")
    csv_path = os.getenv("FRU_CSV_PATH", "/app/data/fridge_sales_with_rating.csv")

    try:
        config = get_db_config()
    except RuntimeError as e:
        error(str(e))
        sys.exit(1)

    info(f"Config: host={config['host']} port={config['port']} db={config['dbname']} verify_only={verify_only} force={force} csv={csv_path}")

    step(f"Connecting to {config['host']}:{config['port']} db={config['dbname']}...")
    try:
        conn = connect_db(config)
    except Exception as e:
        error(f"Connection failed: {e}")
        raise
    success("Connected successfully")

    try:
        if verify_only:
            step("Verify-only mode: checking fru_sales_embeddings count")
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings;")
                count = cur.fetchone()[0]
            success(f"fru_sales_embeddings has {count} rows")
            info(f"FRU_EMBEDDINGS_COUNT={count}")
            info("(verify-only) Emitting FRU_EMBEDDINGS_COUNT for log parsing; flushing stdout")
            sys.stdout.flush()
            return

        step("Phase 1: Applying schema...")
        apply_schema(conn, schema_path="/app/schema.sql", force=force)

        step("Phase 2: Loading fru_sales_raw from CSV...")
        csv_path = _get_optional("FRU_CSV_PATH", "/app/data/fridge_sales_with_rating.csv")
        load_raw_from_csv(conn, csv_path=csv_path, force=force)

        step("Phase 3: Loading embeddings via OpenAI API (from fru_sales_raw)...")
        count = load_embeddings(conn, csv_path=None, config=config, force=force)

        # Output parseable count for verification (info ensures bracketed timestamp for log parsing)
        info(f"About to emit FRU_EMBEDDINGS_COUNT (count={count})")
        success(f"Done. FRU_EMBEDDINGS_COUNT={count}")
        info(f"FRU_EMBEDDINGS_COUNT={count}")
        info("Emitting FRU_EMBEDDINGS_COUNT complete; flushing stdout")
        sys.stdout.flush()
    finally:
        conn.close()
        info("Connection closed")


if __name__ == "__main__":
    try:
        main()
        success("Job completed successfully")
    except Exception as e:
        import traceback
        error(f"Job failed: {e}")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
