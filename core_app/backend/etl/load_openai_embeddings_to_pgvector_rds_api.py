#!/usr/bin/env python3
"""
Load CSV → fru_sales_raw → fru_sales_embeddings scalars → dual-profile embed sync.

Uses AWS RDS Data API (no direct TCP). Vectors via embedding_sync_rds (all credentialed profiles).

Applicable environment: [aws bootstrap]
"""
from __future__ import annotations

import os

import pandas as pd

from backend.services.embedding_sync_rds import (
    RdsDataConnection,
    copy_raw_to_embeddings_scalars_rds,
    format_sql_literal,
    get_rds_data_client,
    sync_all_embeddings_rds,
)
from backend.utils.env_helpers import get_optional_env, get_required_env


def load_raw_from_csv(rds_client, cluster_arn, secret_arn, db_name, csv_path, force=False):
    """Load CSV into fru_sales_raw. Skips if data exists and not force."""
    if not force:
        try:
            resp = rds_client.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=db_name,
                sql="SELECT COUNT(*) FROM fru_sales_raw;",
            )
            cnt = 0
            if resp.get("records") and len(resp["records"]) > 0:
                cnt = int(resp["records"][0][0].get("longValue", 0))
            if cnt > 0:
                print(f"fru_sales_raw already has {cnt} rows; skipping (use force to reload)")
                return cnt
        except Exception:
            pass

    df = pd.read_csv(csv_path)
    required = [
        "ID", "CUSTOMER_ID", "BRAND", "FRIDGE_MODEL", "CAPACITY_LITERS", "PRICE",
        "SALES_DATE", "STORE_NAME", "STORE_ADDRESS", "CUSTOMER_FEEDBACK",
        "FEEDBACK_RATING", "FEEDBACK_SENTIMENT_CATEGORY",
    ]
    for c in required:
        if c not in df.columns:
            raise RuntimeError(f"Missing required column: {c}")

    rows = df.to_dict(orient="records")
    for r in rows:
        cleaned = {k: (None if pd.isna(v) else v) for k, v in r.items()}
        fr = cleaned.get("FEEDBACK_RATING")
        try:
            fr_int = int(fr) if fr is not None else None
        except (ValueError, TypeError):
            fr_int = None
        sql = f"""
        INSERT INTO fru_sales_raw
        (id, customer_id, brand, fridge_model, capacity_liters, price, sales_date,
         store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category)
        VALUES (
            {format_sql_literal(cleaned['ID'])},
            {format_sql_literal(cleaned.get('CUSTOMER_ID', ''))},
            {format_sql_literal(cleaned['BRAND'])},
            {format_sql_literal(cleaned['FRIDGE_MODEL'])},
            {format_sql_literal(cleaned.get('CAPACITY_LITERS'))},
            {format_sql_literal(cleaned['PRICE'])},
            {format_sql_literal(cleaned['SALES_DATE'])},
            {format_sql_literal(cleaned['STORE_NAME'])},
            {format_sql_literal(cleaned.get('STORE_ADDRESS', ''))},
            {format_sql_literal(cleaned.get('CUSTOMER_FEEDBACK', ''))},
            {fr_int if fr_int is not None else 'NULL'},
            {format_sql_literal(cleaned.get('FEEDBACK_SENTIMENT_CATEGORY', ''))}
        )
        ON CONFLICT (id) DO UPDATE SET
          customer_id = EXCLUDED.customer_id, brand = EXCLUDED.brand, fridge_model = EXCLUDED.fridge_model,
          capacity_liters = EXCLUDED.capacity_liters, price = EXCLUDED.price, sales_date = EXCLUDED.sales_date,
          store_name = EXCLUDED.store_name, store_address = EXCLUDED.store_address,
          customer_feedback = EXCLUDED.customer_feedback, feedback_rating = EXCLUDED.feedback_rating,
          feedback_sentiment_category = EXCLUDED.feedback_sentiment_category;
        """
        rds_client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=db_name,
            sql=sql,
        )
    print(f"Loaded {len(rows)} rows into fru_sales_raw")
    return len(rows)


def main():
    csv_path = get_optional_env("FRU_CSV_PATH", "data/raw/fridge_sales_with_rating.csv")
    cluster_arn = get_required_env("DB_CLUSTER_ARN", "Aurora cluster ARN")
    secret_arn = get_required_env("DB_SECRET_ARN", "Aurora secret ARN")
    db_name = get_optional_env("PGDATABASE", "fru_db")
    force = os.environ.get("FRU_FORCE_REFRESH_DATA", "").lower() in ("1", "true", "yes")

    rds_client = get_rds_data_client()
    conn = RdsDataConnection(rds_client, cluster_arn, secret_arn, db_name)

    print("Phase 1: Loading fru_sales_raw from CSV...")
    load_raw_from_csv(rds_client, cluster_arn, secret_arn, db_name, csv_path, force=force)

    if not force:
        try:
            resp = rds_client.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=db_name,
                sql="SELECT COUNT(*) FROM fru_sales_embeddings;",
            )
            cnt = 0
            if resp.get("records") and len(resp["records"]) > 0:
                cnt = int(resp["records"][0][0].get("longValue", 0))
            if cnt > 0:
                print(f"fru_sales_embeddings already has {cnt} rows; skipping (use force to reload)")
                return
        except Exception:
            pass

    print("Phase 2: Copying scalars to fru_sales_embeddings...")
    scalar_count = copy_raw_to_embeddings_scalars_rds(conn)
    print(f"Upserted {scalar_count} scalar rows into fru_sales_embeddings")

    print("Phase 3: Dual-profile embedding sync (all credentialed profiles)...")
    result = sync_all_embeddings_rds(conn, missing_only=False, force=force)
    print(result.to_dict())

    if result.failed > 0:
        raise RuntimeError(f"Embedding sync completed with {result.failed} failures")

    print("Done.")


if __name__ == "__main__":
    main()
