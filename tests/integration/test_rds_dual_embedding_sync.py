"""Integration: dual-profile embedding_sync via RDS Data API (requires Aurora)."""
import os

import pytest


@pytest.mark.integration
def test_rds_sync_populates_both_columns():
    if not os.environ.get("DB_CLUSTER_ARN", "").strip():
        pytest.skip("DB_CLUSTER_ARN not set")
    if not os.environ.get("DB_SECRET_ARN", "").strip():
        pytest.skip("DB_SECRET_ARN not set")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        pytest.skip("OPENAI_API_KEY not set")

    from backend.services.embedding_sync_rds import (
        RdsDataConnection,
        format_sql_string,
        get_rds_data_client,
        sync_embeddings_for_ids_rds,
    )

    cluster = os.environ["DB_CLUSTER_ARN"]
    secret = os.environ["DB_SECRET_ARN"]
    db_name = os.environ.get("PGDATABASE", "fru_db")
    client = get_rds_data_client()
    conn = RdsDataConnection(client, cluster, secret, db_name)

    rid = "INT_RDS_TEST_1"
    client.execute_statement(
        resourceArn=cluster,
        secretArn=secret,
        database=db_name,
        sql=f"""
        INSERT INTO fru_sales_embeddings (id, customer_feedback, brand, fridge_model, price, store_name)
        VALUES ({format_sql_string(rid)}, 'integration test feedback', 'B', 'M', 1.0, 'S')
        ON CONFLICT (id) DO UPDATE SET customer_feedback = EXCLUDED.customer_feedback
        """,
    )

    result = sync_embeddings_for_ids_rds(conn, [rid], force=True)
    assert result.failed == 0
    assert result.embedded >= 1

    cols = ["embedding_openai_1536"]
    if os.environ.get("ARK_API_KEY", "").strip() and os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip():
        cols.append("embedding_skylark_2048")

    for col in cols:
        resp = client.execute_statement(
            resourceArn=cluster,
            secretArn=secret,
            database=db_name,
            sql=f"SELECT {col} IS NOT NULL FROM fru_sales_embeddings WHERE id = {format_sql_string(rid)}",
        )
        assert resp["records"][0][0].get("booleanValue") is True

    client.execute_statement(
        resourceArn=cluster,
        secretArn=secret,
        database=db_name,
        sql=f"DELETE FROM fru_sales_embeddings WHERE id = {format_sql_string(rid)}",
    )


@pytest.mark.integration
def test_rds_sync_missing_only_fills_gap_column():
    if not os.environ.get("DB_CLUSTER_ARN", "").strip():
        pytest.skip("DB_CLUSTER_ARN not set")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        pytest.skip("OPENAI_API_KEY not set")
    if not os.environ.get("ARK_API_KEY", "").strip():
        pytest.skip("ARK_API_KEY not set for skylark gap test")

    from backend.services.embedding_sync_rds import (
        RdsDataConnection,
        get_rds_data_client,
        sync_all_embeddings_rds,
    )

    pytest.skip("Operator-only: requires pre-seeded row with openai only")
