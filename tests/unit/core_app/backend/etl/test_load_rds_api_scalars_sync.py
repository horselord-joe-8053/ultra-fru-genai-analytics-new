"""Unit tests for RDS API ETL loader (dual-column bootstrap)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[5]
_LOADER = _REPO / "core_app/backend/etl/load_openai_embeddings_to_pgvector_rds_api.py"


def test_rds_loader_no_legacy_embedding_column():
    source = _LOADER.read_text()
    assert "execute_insert_via_rds_api" not in source
    assert ", embedding)" not in source
    assert "SET embedding =" not in source


def test_rds_loader_no_openai_only_embed_loop_in_main():
    source = _LOADER.read_text()
    assert "embed_texts" not in source
    assert "sync_all_embeddings_rds" in source


def test_rds_loader_no_profile_flag_or_active_profile():
    source = _LOADER.read_text()
    assert "--profile" not in source
    assert "EMBEDDING_ACTIVE_PROFILE" not in source


def test_rds_scalar_upsert_sql_matches_shared_tuple_shape():
    from backend.services.embedding_sync import SCALAR_UPSERT_SQL
    from backend.services.embedding_sync_rds import scalar_upsert_sql_from_row

    sql = scalar_upsert_sql_from_row({"ID": "F1", "BRAND": "B", "FRIDGE_MODEL": "M", "PRICE": 1.0})
    for col in (
        "customer_id", "brand", "fridge_model", "capacity_liters", "price", "sales_date",
        "store_name", "store_address", "customer_feedback", "feedback_rating",
        "feedback_sentiment_category",
    ):
        assert col in sql
    assert "embedding_openai_1536" not in SCALAR_UPSERT_SQL


def test_rds_main_calls_load_raw_then_scalar_then_sync(monkeypatch):
    monkeypatch.setenv("DB_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setenv("DB_SECRET_ARN", "arn:secret")
    monkeypatch.setenv("CLOUD_REGION", "us-east-1")
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    order = []

    with patch("backend.etl.load_openai_embeddings_to_pgvector_rds_api.load_raw_from_csv") as mock_raw:
        mock_raw.return_value = 10
        with patch(
            "backend.etl.load_openai_embeddings_to_pgvector_rds_api.copy_raw_to_embeddings_scalars_rds",
            side_effect=lambda c: order.append("scalars") or 10,
        ):
            with patch(
                "backend.etl.load_openai_embeddings_to_pgvector_rds_api.sync_all_embeddings_rds",
                side_effect=lambda *a, **k: order.append("sync") or MagicMock(failed=0, to_dict=dict),
            ):
                with patch(
                    "backend.etl.load_openai_embeddings_to_pgvector_rds_api.get_rds_data_client",
                    return_value=MagicMock(),
                ):
                    import importlib
                    mod = importlib.import_module(
                        "backend.etl.load_openai_embeddings_to_pgvector_rds_api"
                    )
                    mod.main()

    assert order == ["scalars", "sync"]


def test_rds_main_skips_when_count_positive_and_not_force(monkeypatch):
    monkeypatch.setenv("DB_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setenv("DB_SECRET_ARN", "arn:secret")
    monkeypatch.setenv("CLOUD_REGION", "us-east-1")

    client = MagicMock()
    client.execute_statement.return_value = {"records": [[{"longValue": 5}]]}

    with patch(
        "backend.etl.load_openai_embeddings_to_pgvector_rds_api.get_rds_data_client",
        return_value=client,
    ):
        with patch(
            "backend.etl.load_openai_embeddings_to_pgvector_rds_api.load_raw_from_csv",
            return_value=5,
        ):
            with patch(
                "backend.etl.load_openai_embeddings_to_pgvector_rds_api.copy_raw_to_embeddings_scalars_rds"
            ) as mock_scalars:
                import importlib
                mod = importlib.import_module(
                    "backend.etl.load_openai_embeddings_to_pgvector_rds_api"
                )
                mod.main()
    mock_scalars.assert_not_called()


def test_rds_main_force_refresh_calls_sync_with_force(monkeypatch):
    monkeypatch.setenv("DB_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setenv("DB_SECRET_ARN", "arn:secret")
    monkeypatch.setenv("CLOUD_REGION", "us-east-1")
    monkeypatch.setenv("FRU_FORCE_REFRESH_DATA", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    with patch(
        "backend.etl.load_openai_embeddings_to_pgvector_rds_api.load_raw_from_csv",
        return_value=1,
    ):
        with patch(
            "backend.etl.load_openai_embeddings_to_pgvector_rds_api.copy_raw_to_embeddings_scalars_rds",
            return_value=1,
        ):
            with patch(
                "backend.etl.load_openai_embeddings_to_pgvector_rds_api.sync_all_embeddings_rds"
            ) as mock_sync:
                mock_sync.return_value = MagicMock(failed=0, to_dict=lambda: {})
                with patch(
                    "backend.etl.load_openai_embeddings_to_pgvector_rds_api.get_rds_data_client",
                    return_value=MagicMock(),
                ):
                    import importlib
                    mod = importlib.import_module(
                        "backend.etl.load_openai_embeddings_to_pgvector_rds_api"
                    )
                    mod.main()
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs.get("force") is True
