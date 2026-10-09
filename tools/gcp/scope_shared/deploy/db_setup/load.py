"""
Shared load logic for fru_sales_raw and fru_sales_embeddings.

Flow: load_raw_from_csv → load_scalars_to_embeddings → embedding_sync (vectors).

Scalar load never reads EMBEDDING_ACTIVE_PROFILE; sync populates all credentialed profiles.
"""
import os
import sys

import pandas as pd
from psycopg2.extras import RealDictCursor

try:
    from tools.cloud_shared.logging.logger import info, success, error, step
    from tools.cloud_shared.env import require
except ImportError:
    def _log(prefix: str, file=sys.stdout):
        def out(msg: str):
            print(f"{prefix} {msg}", file=file, flush=True)
        return out
    info = _log("[INFO]")
    success = _log("[SUCCESS]")
    step = _log("==>")
    error = _log("[ERROR]", file=sys.stderr)

    def require(name: str) -> str:
        v = os.getenv(name)
        if not v:
            raise RuntimeError(f"Required env var '{name}' is not set.")
        return v


REQUIRED_COLUMNS = [
    "ID", "CUSTOMER_ID", "BRAND", "FRIDGE_MODEL", "CAPACITY_LITERS", "PRICE",
    "SALES_DATE", "STORE_NAME", "STORE_ADDRESS", "CUSTOMER_FEEDBACK",
    "FEEDBACK_RATING", "FEEDBACK_SENTIMENT_CATEGORY",
]


def _wire_backend_logging_for_bootstrap() -> None:
    """Route backend.services / backend.env_utils INFO logs through neat_logger during bootstrap."""
    import logging

    class _NeatBridge(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            msg = self.format(record)
            if record.levelno >= logging.WARNING:
                error(msg)
            else:
                info(msg)

    backend_log = logging.getLogger("backend")
    if any(isinstance(h, _NeatBridge) for h in backend_log.handlers):
        return
    handler = _NeatBridge()
    handler.setFormatter(logging.Formatter("%(message)s"))
    backend_log.addHandler(handler)
    backend_log.setLevel(logging.INFO)
    backend_log.propagate = False


def load_raw_from_csv(
    conn,
    csv_path: str,
    force: bool = False,
) -> int:
    """
    Load CSV into fru_sales_raw. Idempotent: skips if data exists and not force.
    Returns row count.
    """
    if not force:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fru_sales_raw;")
            existing = cur.fetchone()[0]
        if existing > 0:
            step(f"fru_sales_raw already loaded ({existing} rows); skipping (use force=True to reload)")
            return existing

    if not os.path.exists(csv_path):
        error(f"CSV not found: {csv_path}")
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    step(f"Loading CSV into fru_sales_raw from {csv_path}")
    df = pd.read_csv(csv_path)
    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            error(f"Missing required column: {c}")
            raise RuntimeError(f"Missing required column: {c}")

    rows = df.to_dict(orient="records")
    with conn.cursor() as cur:
        for r in rows:
            cleaned = {k: (None if pd.isna(v) else v) for k, v in r.items()}
            feedback_rating = cleaned.get("FEEDBACK_RATING")
            try:
                feedback_rating_int = int(feedback_rating) if feedback_rating is not None else None
            except (ValueError, TypeError):
                feedback_rating_int = None
            cur.execute(
                """
                INSERT INTO fru_sales_raw
                (id, customer_id, brand, fridge_model, capacity_liters, price, sales_date,
                 store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  customer_id = EXCLUDED.customer_id,
                  brand = EXCLUDED.brand,
                  fridge_model = EXCLUDED.fridge_model,
                  capacity_liters = EXCLUDED.capacity_liters,
                  price = EXCLUDED.price,
                  sales_date = EXCLUDED.sales_date,
                  store_name = EXCLUDED.store_name,
                  store_address = EXCLUDED.store_address,
                  customer_feedback = EXCLUDED.customer_feedback,
                  feedback_rating = EXCLUDED.feedback_rating,
                  feedback_sentiment_category = EXCLUDED.feedback_sentiment_category
                """,
                (
                    cleaned["ID"],
                    cleaned.get("CUSTOMER_ID", ""),
                    cleaned["BRAND"],
                    cleaned["FRIDGE_MODEL"],
                    cleaned.get("CAPACITY_LITERS"),
                    cleaned["PRICE"],
                    cleaned["SALES_DATE"],
                    cleaned["STORE_NAME"],
                    cleaned.get("STORE_ADDRESS", ""),
                    cleaned.get("CUSTOMER_FEEDBACK", ""),
                    feedback_rating_int,
                    cleaned.get("FEEDBACK_SENTIMENT_CATEGORY", ""),
                ),
            )
        conn.commit()
    success(f"Loaded {len(rows)} rows into fru_sales_raw")
    return len(rows)


def _rows_from_csv_or_raw(conn, csv_path: str | None) -> list[dict]:
    if csv_path:
        if not os.path.exists(csv_path):
            error(f"CSV not found: {csv_path}")
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        step(f"Reading CSV scalars from {csv_path}")
        df = pd.read_csv(csv_path)
        return df.to_dict(orient="records")
    step("Reading scalars from fru_sales_raw")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, customer_id, brand, fridge_model, capacity_liters, price, sales_date, "
            "store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category "
            "FROM fru_sales_raw"
        )
        raw_rows = cur.fetchall()
    return [
        {
            "ID": r["id"],
            "CUSTOMER_ID": r.get("customer_id") or "",
            "BRAND": r["brand"],
            "FRIDGE_MODEL": r["fridge_model"],
            "CAPACITY_LITERS": r.get("capacity_liters"),
            "PRICE": r["price"],
            "SALES_DATE": r["sales_date"],
            "STORE_NAME": r["store_name"],
            "STORE_ADDRESS": r.get("store_address") or "",
            "CUSTOMER_FEEDBACK": r.get("customer_feedback") or "",
            "FEEDBACK_RATING": r.get("feedback_rating"),
            "FEEDBACK_SENTIMENT_CATEGORY": r.get("feedback_sentiment_category") or "",
        }
        for r in raw_rows
    ]


def load_scalars_to_embeddings(
    conn,
    csv_path: str | None = None,
    config: dict | None = None,
    force: bool = False,
) -> int:
    """Upsert scalar columns into fru_sales_embeddings (no embedding API)."""
    from backend.services.embedding_sync import scalar_row_tuple, SCALAR_UPSERT_SQL

    if not force:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings;")
            existing = cur.fetchone()[0]
        if existing > 0:
            step(f"Scalars already loaded ({existing} rows); skipping (use force=True to reload)")
            return existing

    rows = _rows_from_csv_or_raw(conn, csv_path)
    if not rows:
        error("No rows to load")
        raise RuntimeError("No rows in fru_sales_raw or CSV")

    for c in REQUIRED_COLUMNS:
        if c not in rows[0]:
            error(f"Missing required column: {c}")
            raise RuntimeError(f"Missing required column: {c}")

    if config:
        step(f"Connecting to DB {config['host']}:{config['port']}/{config['dbname']}")
    step(f"Upserting {len(rows)} scalar rows into fru_sales_embeddings")

    with conn.cursor() as cur:
        for row_data in rows:
            cur.execute(SCALAR_UPSERT_SQL, scalar_row_tuple(row_data))
    conn.commit()
    success(f"Scalar load complete. Total: {len(rows)} rows")
    return len(rows)


def load_embeddings(
    conn,
    csv_path: str | None = None,
    config: dict | None = None,
    force: bool = False,
) -> int:
    """
    Bootstrap: scalars then dual-profile embedding sync.
    Backward-compatible name used by setup_database / run_schema_and_load.
    """
    from backend.services.embedding_sync import copy_raw_to_embeddings_scalars, sync_all_embeddings

    if not force:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings;")
            existing = cur.fetchone()[0]
        if existing > 0:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM fru_sales_embeddings WHERE embedding_openai_1536 IS NOT NULL"
                )
                has_vectors = cur.fetchone()[0]
            if has_vectors > 0:
                step(
                    f"Data already loaded ({existing} rows, {has_vectors} with vectors); "
                    "skipping (use force=True to reload)"
                )
                return existing

    if csv_path:
        load_scalars_to_embeddings(conn, csv_path=csv_path, config=config, force=True)
    else:
        copy_raw_to_embeddings_scalars(conn)

    _wire_backend_logging_for_bootstrap()

    step("Syncing embedding vectors for all available profiles")
    result = sync_all_embeddings(conn, missing_only=False, force=True)
    from backend.services.embedding_sync_log import format_sync_result_detail

    for line in format_sync_result_detail(result):
        if result.failed:
            error(line)
        else:
            info(line)
    if result.failed:
        error(f"Embedding sync failed: {result.failed} row(s); see errors above")
        raise RuntimeError(f"Embedding sync failed: {result.failed} failures")
    success(f"Load complete. Embedded={result.embedded} skipped={result.skipped}")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings;")
        return cur.fetchone()[0]
