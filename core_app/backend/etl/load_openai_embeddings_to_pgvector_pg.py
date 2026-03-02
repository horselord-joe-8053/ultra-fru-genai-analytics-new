#!/usr/bin/env python3
"""
Load CSV data into PostgreSQL (Cloud SQL) via psycopg2.
GCP counterpart to load_openai_embeddings_to_pgvector_rds_api.py (AWS RDS Data API).

DEPRECATED: GCP setup_database now uses tools/gcp/scope_shared/deploy/db_setup/load.py
(load_embeddings) directly. This script remains for standalone CLI use if needed.

Requires: PGHOST, PGPASSWORD, OPENAI_API_KEY, FRU_CSV_PATH.
"""
import os
import time

import pandas as pd
import psycopg2
from openai import OpenAI
from backend.utils.env_helpers import get_optional_env, get_required_env

OPENAI_MODEL = get_required_env("OPENAI_EMBED_MODEL", "OpenAI embedding model")


def get_openai_client() -> OpenAI:
    return OpenAI()


def embed_texts(client: OpenAI, texts):
    resp = client.embeddings.create(model=OPENAI_MODEL, input=texts)
    return [item.embedding for item in resp.data]


def main():
    csv_path = get_optional_env("FRU_CSV_PATH", "data/raw/fridge_sales_with_rating.csv")
    host = get_required_env("PGHOST", "PostgreSQL host")
    port = int(get_optional_env("PGPORT", "5432"))
    user = get_optional_env("PGUSER", "postgres")
    password = get_required_env("PGPASSWORD", "PostgreSQL password")
    dbname = get_optional_env("PGDATABASE", "fru_db")

    df = pd.read_csv(csv_path)
    required = ["ID", "CUSTOMER_ID", "BRAND", "FRIDGE_MODEL", "CAPACITY_LITERS", "PRICE",
                "SALES_DATE", "STORE_NAME", "STORE_ADDRESS", "CUSTOMER_FEEDBACK",
                "FEEDBACK_RATING", "FEEDBACK_SENTIMENT_CATEGORY"]
    for c in required:
        if c not in df.columns:
            raise RuntimeError(f"Missing required column: {c}")

    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=10
    )
    openai_client = get_openai_client()
    rows = df.to_dict(orient="records")
    batch_size = 64
    total_rows = len(rows)
    success_count = 0

    print(f"Processing {total_rows} rows in batches of {batch_size}...")

    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = [r.get("CUSTOMER_FEEDBACK") or "" for r in batch]
            embeddings = embed_texts(openai_client, texts)

            for row_data, embedding in zip(batch, embeddings):
                cleaned = {k: (None if pd.isna(v) else v) for k, v in row_data.items()}
                feedback_rating = cleaned.get("FEEDBACK_RATING")
                try:
                    feedback_rating_int = int(feedback_rating) if feedback_rating is not None else None
                except (ValueError, TypeError):
                    feedback_rating_int = None

                cur.execute("""
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
                """, (
                    cleaned["ID"], cleaned.get("CUSTOMER_ID", ""), cleaned["BRAND"],
                    cleaned["FRIDGE_MODEL"], cleaned.get("CAPACITY_LITERS"),
                    cleaned["PRICE"], cleaned["SALES_DATE"], cleaned["STORE_NAME"],
                    cleaned.get("STORE_ADDRESS", ""), cleaned.get("CUSTOMER_FEEDBACK", ""),
                    feedback_rating_int, cleaned.get("FEEDBACK_SENTIMENT_CATEGORY", ""),
                    str(embedding),
                ))
                success_count += 1
            conn.commit()
            print(f"Processed batch [{i}..{i + len(batch) - 1}]: {len(batch)} rows")
            time.sleep(0.2)

    conn.close()
    print(f"\nDone. Total: {success_count} rows.")


if __name__ == "__main__":
    main()
