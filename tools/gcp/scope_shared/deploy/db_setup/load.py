"""
Shared load logic for fru_sales_raw and fru_sales_embeddings (OpenAI embeddings + psycopg2).

Used by run_schema_and_load.py (container) and setup_database.py (host).
Uses os.getenv() only – no backend.utils.env_helpers (container has no core_app).

Flow: load_raw_from_csv (CSV → fru_sales_raw) then load_embeddings (fru_sales_raw → fru_sales_embeddings).

Container-safe: when run inside the GCP db-setup image, tools/ is not in the image;
we use minimal local stubs for require() and logging so the same code runs on host and in Cloud Run.
"""
import os
import sys
import time

import pandas as pd
from openai import OpenAI
from psycopg2.extras import RealDictCursor

# Use shared tools when available (host); in container (Cloud Run job) tools/ is not in the image
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


def load_embeddings(
    conn,
    csv_path: str | None = None,
    config: dict | None = None,
    force: bool = False,
) -> int:
    """
    Load fru_sales_raw into fru_sales_embeddings via OpenAI embeddings.
    When csv_path is None, reads from fru_sales_raw. When csv_path is given, reads from CSV (legacy).
    Returns row count. Idempotent: skips if data exists and not force.
    """
    openai_model = os.getenv("OPENAI_EMBED_MODEL") or require("OPENAI_EMBED_MODEL")

    # Idempotency: skip if data exists and not force
    if not force:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings;")
            existing = cur.fetchone()[0]
        if existing > 0:
            step(f"Data already loaded ({existing} rows); skipping (use force=True to reload)")
            return existing

    if csv_path:
        if not os.path.exists(csv_path):
            error(f"CSV not found: {csv_path}")
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        step(f"Reading CSV from {csv_path}")
        df = pd.read_csv(csv_path)
        rows = df.to_dict(orient="records")
    else:
        step("Reading from fru_sales_raw")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, customer_id, brand, fridge_model, capacity_liters, price, sales_date, "
                "store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category "
                "FROM fru_sales_raw"
            )
            raw_rows = cur.fetchall()
        # Map lowercase to uppercase keys for compatibility with insert logic
        rows = [
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

    info(f"Loaded {len(rows)} rows for embedding")
    if not rows:
        error("No rows to load")
        raise RuntimeError("No rows in fru_sales_raw or CSV")

    for c in REQUIRED_COLUMNS:
        if c not in rows[0]:
            error(f"Missing required column: {c}")
            raise RuntimeError(f"Missing required column: {c}")

    if config:
        step(f"Connecting to DB {config['host']}:{config['port']}/{config['dbname']}")
    info("Initializing OpenAI client")
    openai_client = OpenAI()
    batch_size = 64
    success_count = 0
    num_batches = (len(rows) + batch_size - 1) // batch_size
    step(f"Processing {len(rows)} rows in {num_batches} batches of {batch_size}")

    with conn.cursor() as cur:
        for batch_idx, i in enumerate(range(0, len(rows), batch_size), 1):
            batch = rows[i : i + batch_size]
            step(f"Batch {batch_idx}/{num_batches}: fetching embeddings from OpenAI...")
            texts = [r.get("CUSTOMER_FEEDBACK") or "" for r in batch]
            try:
                info(f"Calling OpenAI embeddings API (model={openai_model}, n={len(texts)} texts)")
                resp = openai_client.embeddings.create(model=openai_model, input=texts)
                embeddings = [item.embedding for item in resp.data]
            except Exception as e:
                error(f"Batch {batch_idx}/{num_batches} OpenAI call failed: {e}")
                raise

            for row_data, embedding in zip(batch, embeddings):
                cleaned = {k: (None if pd.isna(v) else v) for k, v in row_data.items()}
                feedback_rating = cleaned.get("FEEDBACK_RATING")
                try:
                    feedback_rating_int = int(feedback_rating) if feedback_rating is not None else None
                except (ValueError, TypeError):
                    feedback_rating_int = None

                cur.execute(
                    """
                    INSERT INTO fru_sales_embeddings
                    (id, customer_id, brand, fridge_model, capacity_liters, price, sales_date,
                     store_name, store_address, customer_feedback, feedback_rating,
                     feedback_sentiment_category, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
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
                      feedback_sentiment_category = EXCLUDED.feedback_sentiment_category,
                      embedding = EXCLUDED.embedding
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
                        str(embedding),
                    ),
                )
                success_count += 1
            conn.commit()
            info(f"Batch {batch_idx}/{num_batches} done: inserted {len(batch)} rows (total so far: {success_count})")
            time.sleep(0.2)

    success(f"Load complete. Total: {success_count} rows")
    return success_count
