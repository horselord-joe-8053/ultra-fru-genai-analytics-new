"""
Dual-profile embedding sync for fru_sales_embeddings.

Writes populate every available profile column from embedding_profiles.yaml.
EMBEDDING_ACTIVE_PROFILE is NOT used here — it selects the search/read lane only.

Applicable environment: [local] [aws] [gcp]
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Any

from openai import OpenAI
from psycopg2.extensions import connection as PgConnection

from backend.env_utils.cloud_shared.embedding_profiles import EmbeddingProfile, get_profiles
from backend.services.embedding_sync_core import (
    SyncResult,
    available_profiles,
    profile_has_credentials,
    sync_embeddings_core,
)

# Re-export for backward compatibility
__all__ = [
    "SCALAR_UPSERT_SQL",
    "SyncResult",
    "available_profiles",
    "profile_has_credentials",
    "scalar_row_tuple",
    "upsert_scalar_row",
    "copy_raw_to_embeddings_scalars",
    "sync_embeddings_for_ids",
    "sync_all_embeddings",
    "embedding_column_population_counts",
]

logger = logging.getLogger(__name__)

SCALAR_UPSERT_SQL = """
INSERT INTO fru_sales_embeddings
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
"""


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) or row.get(key.lower() if key.isupper() else key.upper())


def scalar_row_tuple(row: dict[str, Any]) -> tuple:
    """Build INSERT tuple for scalar columns only (no embedding vectors)."""
    feedback_rating = _row_value(row, "FEEDBACK_RATING")
    try:
        feedback_rating_int = int(feedback_rating) if feedback_rating is not None else None
    except (ValueError, TypeError):
        feedback_rating_int = None
    price = _row_value(row, "PRICE")
    return (
        str(_row_value(row, "ID") or _row_value(row, "id")),
        str(_row_value(row, "CUSTOMER_ID") or ""),
        str(_row_value(row, "BRAND") or "Unknown"),
        str(_row_value(row, "FRIDGE_MODEL") or "Unknown"),
        _row_value(row, "CAPACITY_LITERS"),
        float(price) if price is not None else 0.0,
        _row_value(row, "SALES_DATE"),
        str(_row_value(row, "STORE_NAME") or "Unknown"),
        str(_row_value(row, "STORE_ADDRESS") or ""),
        str(_row_value(row, "CUSTOMER_FEEDBACK") or ""),
        feedback_rating_int,
        str(_row_value(row, "FEEDBACK_SENTIMENT_CATEGORY") or "Neutral"),
    )


def upsert_scalar_row(conn: PgConnection, row: dict[str, Any]) -> str:
    """Upsert scalar fields into fru_sales_embeddings. Returns row id."""
    row_id = str(_row_value(row, "ID") or _row_value(row, "id"))
    with conn.cursor() as cur:
        cur.execute(SCALAR_UPSERT_SQL, scalar_row_tuple(row))
    conn.commit()
    return row_id


def copy_raw_to_embeddings_scalars(conn: PgConnection) -> int:
    """Copy scalar columns from fru_sales_raw into fru_sales_embeddings."""
    sql = """
    INSERT INTO fru_sales_embeddings
    (id, customer_id, brand, fridge_model, capacity_liters, price, sales_date,
     store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category)
    SELECT id, customer_id, brand, fridge_model, capacity_liters, price, sales_date,
           store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category
    FROM fru_sales_raw
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
    with conn.cursor() as cur:
        cur.execute(sql)
        count = cur.rowcount
    conn.commit()
    return count


def _fetch_rows_for_ids(conn: PgConnection, ids: list[str]) -> dict[str, tuple[str, dict[str, Any]]]:
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, customer_feedback, "
            + ", ".join(p.pgvector_column for p in get_profiles().values())
            + " FROM fru_sales_embeddings WHERE id = ANY(%s)",
            (ids,),
        )
        rows = cur.fetchall()
    colnames = ["id", "customer_feedback"] + [p.pgvector_column for p in get_profiles().values()]
    out: dict[str, tuple[str, dict[str, Any]]] = {}
    for row in rows:
        data = dict(zip(colnames, row))
        rid = str(data["id"])
        out[rid] = (data.get("customer_feedback") or "", data)
    return out


def sync_embeddings_for_ids(
    conn: PgConnection,
    ids: list[str],
    *,
    profiles: list[str] | None = None,
    force: bool = False,
    openai_client: OpenAI | None = None,
) -> SyncResult:
    """Embed customer_feedback for given ids across all available profiles."""
    row_map = _fetch_rows_for_ids(conn, ids)

    def write_vector(prof: EmbeddingProfile, rid: str, vector: list[float]) -> None:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE fru_sales_embeddings SET {prof.pgvector_column} = %s::vector WHERE id = %s",
                (str(vector), rid),
            )
        conn.commit()

    return sync_embeddings_core(
        ids,
        row_map,
        profiles=profiles,
        force=force,
        openai_client=openai_client,
        write_vector=write_vector,
    )


def _ids_missing_any_profile(conn: PgConnection, target_profiles: list[EmbeddingProfile]) -> list[str]:
    if not target_profiles:
        return []
    conditions = " OR ".join(f"{p.pgvector_column} IS NULL" for p in target_profiles)
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM fru_sales_embeddings WHERE {conditions} ORDER BY id")
        return [str(r[0]) for r in cur.fetchall()]


def sync_all_embeddings(
    conn: PgConnection,
    *,
    missing_only: bool = True,
    force: bool = False,
    profiles: list[str] | None = None,
    batch_size: int = 64,
    openai_client: OpenAI | None = None,
) -> SyncResult:
    """Sync embeddings for all rows (or rows missing any profile column)."""
    aggregate = SyncResult()
    target_profiles = available_profiles(profiles)

    if missing_only and not force:
        ids = _ids_missing_any_profile(conn, target_profiles)
    else:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM fru_sales_embeddings ORDER BY id")
            ids = [str(r[0]) for r in cur.fetchall()]

    if not ids:
        return aggregate

    total_batches = (len(ids) + batch_size - 1) // batch_size
    logger.info(
        "embedding_sync_all: rows=%d batches=%d batch_size=%d profiles=%s",
        len(ids),
        total_batches,
        batch_size,
        [p.name for p in target_profiles],
    )

    for i in range(0, len(ids), batch_size):
        batch_num = i // batch_size + 1
        batch = ids[i : i + batch_size]
        logger.info(
            "embedding_sync_all: batch %d/%d ids=%d..%d (n=%d)",
            batch_num,
            total_batches,
            i + 1,
            i + len(batch),
            len(batch),
        )
        batch_result = sync_embeddings_for_ids(
            conn,
            batch,
            profiles=profiles,
            force=force,
            openai_client=openai_client,
        )
        aggregate.embedded += batch_result.embedded
        aggregate.skipped += batch_result.skipped
        aggregate.failed += batch_result.failed
        aggregate.warnings.extend(batch_result.warnings)
        aggregate.errors.extend(batch_result.errors)
        for name, counts in batch_result.per_profile.items():
            agg = aggregate.per_profile.setdefault(name, {"embedded": 0, "skipped": 0, "failed": 0})
            for k, v in counts.items():
                agg[k] += v
        logger.info(
            "embedding_sync_all: batch %d/%d cumulative embedded=%d failed=%d",
            batch_num,
            total_batches,
            aggregate.embedded,
            aggregate.failed,
        )
        time.sleep(0.2)

    return aggregate


def embedding_column_population_counts(conn: PgConnection) -> dict[str, int]:
    """COUNT non-null rows per profile column (for /health)."""
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fru_sales_embeddings")
        counts["total_rows"] = cur.fetchone()[0]
        for prof in get_profiles().values():
            cur.execute(
                f"SELECT COUNT(*) FROM fru_sales_embeddings WHERE {prof.pgvector_column} IS NOT NULL"
            )
            counts[prof.name] = cur.fetchone()[0]
    return counts


def main(argv: list[str] | None = None) -> int:
    from backend.utils.env_helpers import get_optional_int_env, get_required_env
    import psycopg2

    parser = argparse.ArgumentParser(description="Sync embedding vectors from DB customer_feedback.")
    parser.add_argument("--all", action="store_true", help="Sync all rows (see --missing-only)")
    parser.add_argument("--ids", help="Comma-separated row ids")
    parser.add_argument("--missing-only", action="store_true", default=False)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--profiles", help="Comma-separated profile names (default: all with creds)")
    args = parser.parse_args(argv)

    profile_list = [p.strip() for p in args.profiles.split(",")] if args.profiles else None
    conn = psycopg2.connect(
        host=get_required_env("PGHOST", "Database host"),
        port=get_optional_int_env("PGPORT", 5432),
        user=get_required_env("PGUSER", "Database username"),
        password=get_required_env("PGPASSWORD", "Database password"),
        dbname=get_required_env("PGDATABASE", "Database name"),
    )
    try:
        if args.ids:
            ids = [x.strip() for x in args.ids.split(",") if x.strip()]
            result = sync_embeddings_for_ids(conn, ids, profiles=profile_list, force=args.force)
        elif args.all:
            result = sync_all_embeddings(
                conn,
                missing_only=args.missing_only,
                force=args.force,
                profiles=profile_list,
            )
        else:
            parser.error("Specify --all or --ids")
            return 2
        print(result.to_dict())
        return 0 if result.failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
