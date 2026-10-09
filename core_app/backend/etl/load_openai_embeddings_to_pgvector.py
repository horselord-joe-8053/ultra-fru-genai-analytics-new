#!/usr/bin/env python3
"""
Load CSV scalar data into fru_sales_embeddings (no embedding API calls).

Vectors are populated separately via backend.services.embedding_sync.

Applicable environment: [local] [aws {ecs | eks}] [azure {aci | aks}] [gcp {cloud-run | gke}]
"""
import argparse
import os
import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from backend.services.embedding_sync import scalar_row_tuple, sync_all_embeddings
from backend.utils.env_helpers import get_optional_env, get_optional_int_env, get_required_env

REQUIRED_COLUMNS = [
    "ID",
    "CUSTOMER_ID",
    "BRAND",
    "FRIDGE_MODEL",
    "CAPACITY_LITERS",
    "PRICE",
    "SALES_DATE",
    "STORE_NAME",
    "STORE_ADDRESS",
    "CUSTOMER_FEEDBACK",
    "FEEDBACK_RATING",
    "FEEDBACK_SENTIMENT_CATEGORY",
]

SCALAR_UPSERT_SQL = """
INSERT INTO fru_sales_embeddings
(id, customer_id, brand, fridge_model, capacity_liters, price, sales_date, store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
"""


def main():
    parser = argparse.ArgumentParser(
        description="Load CSV scalars into fru_sales_embeddings (optional --sync-embeddings)."
    )
    parser.add_argument(
        "--sync-embeddings",
        action="store_true",
        help="After scalar load, run embedding_sync.sync_all_embeddings on all rows",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="With --sync-embeddings: only fill NULL profile columns",
    )
    args = parser.parse_args()

    csv_path = get_optional_env("FRU_CSV_PATH", "data/raw/fridge_sales_with_rating.csv")
    df = pd.read_csv(csv_path)

    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            raise RuntimeError(f"Missing required column: {c}")

    conn = psycopg2.connect(
        host=get_required_env("PGHOST", "Database host"),
        port=get_optional_int_env("PGPORT", 5432),
        user=get_required_env("PGUSER", "Database username"),
        password=get_required_env("PGPASSWORD", "Database password"),
        dbname=get_required_env("PGDATABASE", "Database name"),
    )
    conn.autocommit = True
    cur = conn.cursor()

    rows = df.to_dict(orient="records")
    batch_size = 64

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        payload = [scalar_row_tuple(r) for r in batch]
        execute_batch(cur, SCALAR_UPSERT_SQL, payload)
        print(f"Upserted scalars {len(payload)} rows [{i}..{i + len(payload) - 1}]")
        time.sleep(0.1)

    cur.close()

    if args.sync_embeddings:
        conn.autocommit = False
        result = sync_all_embeddings(
            conn,
            missing_only=args.missing_only,
            force=not args.missing_only,
        )
        print(f"Embedding sync: {result.to_dict()}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
