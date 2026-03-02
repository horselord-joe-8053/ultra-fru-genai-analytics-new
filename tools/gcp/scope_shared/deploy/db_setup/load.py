"""
Shared load logic for fru_sales_embeddings (OpenAI embeddings + psycopg2).

Used by run_schema_and_load.py (container) and setup_database.py (host).
Uses os.getenv() only – no backend.utils.env_helpers (container has no core_app).
"""
import os
import time

import pandas as pd
from openai import OpenAI

REQUIRED_COLUMNS = [
    "ID", "CUSTOMER_ID", "BRAND", "FRIDGE_MODEL", "CAPACITY_LITERS", "PRICE",
    "SALES_DATE", "STORE_NAME", "STORE_ADDRESS", "CUSTOMER_FEEDBACK",
    "FEEDBACK_RATING", "FEEDBACK_SENTIMENT_CATEGORY",
]


def load_embeddings(
    conn,
    csv_path: str,
    config: dict | None = None,
    force: bool = False,
) -> int:
    """
    Load CSV into fru_sales_embeddings via OpenAI embeddings.
    Returns row count. Idempotent: skips if data exists and not force.
    """
    from tools.cloud_shared.logging.logger import info, success, error, step

    openai_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    # Idempotency: skip if data exists and not force
    if not force:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings;")
            existing = cur.fetchone()[0]
        if existing > 0:
            step(f"Data already loaded ({existing} rows); skipping (use force=True to reload)")
            return existing

    if not os.path.exists(csv_path):
        error(f"CSV not found: {csv_path}")
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    step(f"Reading CSV from {csv_path}")
    df = pd.read_csv(csv_path)
    info(f"Loaded {len(df)} rows from CSV")

    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            error(f"Missing required column: {c}")
            raise RuntimeError(f"Missing required column: {c}")

    if config:
        step(f"Connecting to DB {config['host']}:{config['port']}/{config['dbname']}")
    info("Initializing OpenAI client")
    openai_client = OpenAI()
    rows = df.to_dict(orient="records")
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
