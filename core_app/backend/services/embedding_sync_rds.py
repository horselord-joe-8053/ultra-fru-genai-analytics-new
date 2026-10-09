"""
Dual-profile embedding sync via AWS RDS Data API (bootstrap / no TCP to Aurora).

Same storage rules as embedding_sync.py; transport uses execute_statement.
Never reads EMBEDDING_ACTIVE_PROFILE.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError
from openai import OpenAI

from backend.env_utils.cloud_shared.embedding_profiles import EmbeddingProfile, get_profiles
from backend.services.embedding_sync import scalar_row_tuple
from backend.services.embedding_sync_core import (
    SyncResult,
    available_profiles,
    sync_embeddings_core,
)

logger = logging.getLogger(__name__)


def parse_rds_field(field: dict | None) -> Any:
    """Parse RDS Data API field dict to Python value."""
    if not field or field.get("isNull"):
        return None
    for key in ("stringValue", "longValue", "doubleValue", "booleanValue"):
        if key in field:
            return field[key]
    if "blobValue" in field:
        return field["blobValue"]
    return None


def format_sql_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def format_sql_literal(value: Any) -> str:
    """Format a Python value for inline SQL (RDS Data API has no bind params)."""
    import math

    if value is None:
        return "NULL"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "NULL"
    if isinstance(value, str):
        if value.lower() == "nan" or value == "":
            return "NULL"
        return format_sql_string(value)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return format_sql_string(str(value))


def vector_to_pg_literal(vector: list[float]) -> str:
    """PostgreSQL vector literal for ::vector cast."""
    return f"'[{','.join(map(str, vector))}]'"


class RdsDataConnection:
    """Minimal RDS Data API session for embedding sync."""

    def __init__(
        self,
        rds_client,
        cluster_arn: str,
        secret_arn: str,
        db_name: str,
    ):
        self.rds_client = rds_client
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.db_name = db_name

    def execute(self, sql: str) -> dict:
        return self.rds_client.execute_statement(
            resourceArn=self.cluster_arn,
            secretArn=self.secret_arn,
            database=self.db_name,
            sql=sql,
        )


def get_rds_data_client(region: str | None = None):
    region = (region or os.environ.get("CLOUD_REGION", "")).strip()
    profile = os.environ.get("AWS_PROFILE", "").strip()
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client("rds-data", region_name=region)


def _fetch_rows_for_ids_rds(conn: RdsDataConnection, ids: list[str]) -> dict[str, tuple[str, dict[str, Any]]]:
    if not ids:
        return {}
    id_list = ", ".join(format_sql_string(str(i)) for i in ids)
    cols = ", ".join(p.pgvector_column for p in get_profiles().values())
    sql = (
        f"SELECT id, customer_feedback, {cols} "
        f"FROM fru_sales_embeddings WHERE id IN ({id_list})"
    )
    resp = conn.execute(sql)
    colnames = ["id", "customer_feedback"] + [p.pgvector_column for p in get_profiles().values()]
    out: dict[str, tuple[str, dict[str, Any]]] = {}
    for rec in resp.get("records", []):
        vals = [parse_rds_field(f) for f in rec]
        data = dict(zip(colnames, vals))
        rid = str(data["id"])
        out[rid] = (data.get("customer_feedback") or "", data)
    return out


def _update_vector_rds(conn: RdsDataConnection, prof: EmbeddingProfile, rid: str, vector: list[float]) -> None:
    sql = (
        f"UPDATE fru_sales_embeddings SET {prof.pgvector_column} = "
        f"{vector_to_pg_literal(vector)}::vector WHERE id = {format_sql_string(rid)}"
    )
    conn.execute(sql)


def sync_embeddings_for_ids_rds(
    conn: RdsDataConnection,
    ids: list[str],
    *,
    profiles: list[str] | None = None,
    force: bool = False,
    openai_client: OpenAI | None = None,
) -> SyncResult:
    row_map = _fetch_rows_for_ids_rds(conn, ids)

    def write_vector(prof: EmbeddingProfile, rid: str, vector: list[float]) -> None:
        _update_vector_rds(conn, prof, rid, vector)

    return sync_embeddings_core(
        ids,
        row_map,
        profiles=profiles,
        force=force,
        openai_client=openai_client,
        write_vector=write_vector,
    )


def _ids_missing_any_profile_rds(
    conn: RdsDataConnection, target_profiles: list[EmbeddingProfile]
) -> list[str]:
    if not target_profiles:
        return []
    conditions = " OR ".join(f"{p.pgvector_column} IS NULL" for p in target_profiles)
    resp = conn.execute(f"SELECT id FROM fru_sales_embeddings WHERE {conditions} ORDER BY id")
    return [str(parse_rds_field(rec[0])) for rec in resp.get("records", [])]


def sync_all_embeddings_rds(
    conn: RdsDataConnection,
    *,
    missing_only: bool = True,
    force: bool = False,
    profiles: list[str] | None = None,
    batch_size: int = 64,
    openai_client: OpenAI | None = None,
) -> SyncResult:
    aggregate = SyncResult()
    target_profiles = available_profiles(profiles)

    if missing_only and not force:
        ids = _ids_missing_any_profile_rds(conn, target_profiles)
    else:
        resp = conn.execute("SELECT id FROM fru_sales_embeddings ORDER BY id")
        ids = [str(parse_rds_field(rec[0])) for rec in resp.get("records", [])]

    if not ids:
        return aggregate

    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        batch_result = sync_embeddings_for_ids_rds(
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
        time.sleep(0.2)

    return aggregate


def scalar_upsert_sql_from_row(row: dict[str, Any]) -> str:
    """Build inline SQL for scalar upsert (no embedding columns)."""
    t = scalar_row_tuple(row)
    values = ", ".join(format_sql_literal(v) for v in t)
    return f"""
INSERT INTO fru_sales_embeddings
(id, customer_id, brand, fridge_model, capacity_liters, price, sales_date,
 store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category)
VALUES ({values})
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


def upsert_scalar_row_rds(conn: RdsDataConnection, row: dict[str, Any]) -> str:
    conn.execute(scalar_upsert_sql_from_row(row))
    return str(row.get("ID") or row.get("id"))


def copy_raw_to_embeddings_scalars_rds(conn: RdsDataConnection) -> int:
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
    conn.execute(sql)
    resp = conn.execute("SELECT COUNT(*) FROM fru_sales_raw")
    if resp.get("records"):
        return int(parse_rds_field(resp["records"][0][0]) or 0)
    return 0


def apply_migrations_rds(conn: RdsDataConnection, migrations_dir: str | None = None) -> None:
    """Apply SQL migration files via RDS Data API (idempotent)."""
    from tools.cloud_shared.deploy.setup_database_utils import get_repo_root

    root = migrations_dir or os.path.join(get_repo_root(), "core_app", "sql", "migrations")
    if not os.path.isdir(root):
        return
    files = sorted(f for f in os.listdir(root) if f.endswith(".sql"))
    for fname in files:
        path = os.path.join(root, fname)
        with open(path) as f:
            sql = f.read()
        try:
            conn.execute(sql)
            logger.info("Migration applied via RDS Data API: %s", fname)
        except ClientError as e:
            raise RuntimeError(f"Migration {fname} failed: {e}") from e
