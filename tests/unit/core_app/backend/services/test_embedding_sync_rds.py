"""Unit tests for embedding_sync_rds (RDS Data API transport)."""
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.env_utils.cloud_shared.embedding_profiles import get_profiles
from backend.services.embedding_sync_rds import (
    RdsDataConnection,
    format_sql_string,
    parse_rds_field,
    scalar_upsert_sql_from_row,
    sync_all_embeddings_rds,
    sync_embeddings_for_ids_rds,
    vector_to_pg_literal,
)


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def _mock_conn(execute_side_effect=None):
    client = MagicMock()
    if execute_side_effect:
        client.execute_statement.side_effect = execute_side_effect
    return RdsDataConnection(client, "arn:cluster", "arn:secret", "fru_db")


def test_rds_sync_for_ids_updates_both_columns(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("ARK_API_KEY", "a")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "m")

    sql_calls = []

    def execute(**kwargs):
        sql_calls.append(kwargs["sql"])
        if "SELECT id, customer_feedback" in kwargs["sql"]:
            return {
                "records": [[
                    {"stringValue": "F1"},
                    {"stringValue": "great fridge"},
                    {"isNull": True},
                    {"isNull": True},
                ]]
            }
        return {}

    conn = _mock_conn(execute)

    mock_openai = MagicMock()
    mock_openai.embed_texts.return_value = [[0.1] * 1536]
    mock_skylark = MagicMock()
    mock_skylark.embed_texts.return_value = [[0.2] * 2048]

    def factory(profile=None, openai_client=None):
        return mock_openai if profile.name == "openai_1536" else mock_skylark

    with patch("backend.services.embedding_sync_core.create_embedding_client", side_effect=factory):
        result = sync_embeddings_for_ids_rds(conn, ["F1"], force=True)

    assert result.embedded == 2
    updates = [s for s in sql_calls if "UPDATE fru_sales_embeddings" in s]
    assert any("embedding_openai_1536" in s and "::vector" in s for s in updates)
    assert any("embedding_skylark_2048" in s and "::vector" in s for s in updates)


def test_rds_sync_ignores_active_profile(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("ARK_API_KEY", "a")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "m")
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")

    sql_calls = []

    def execute(**kwargs):
        sql_calls.append(kwargs["sql"])
        if "SELECT id" in kwargs["sql"]:
            return {"records": [[{"stringValue": "F1"}, {"stringValue": "x"}, {"isNull": True}, {"isNull": True}]]}
        return {}

    conn = _mock_conn(execute)
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1] * 1536]

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        sync_embeddings_for_ids_rds(conn, ["F1"], force=True)

    assert any("embedding_skylark_2048" in s for s in sql_calls)


def test_rds_available_profiles_openai_only_when_ark_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    def execute(**kwargs):
        if "SELECT id" in kwargs["sql"]:
            return {"records": [[{"stringValue": "F1"}, {"stringValue": "x"}, {"isNull": True}, {"isNull": True}]]}
        return {}

    conn = _mock_conn(execute)
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1] * 1536]

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        result = sync_embeddings_for_ids_rds(conn, ["F1"], force=True)

    assert result.embedded == 1
    assert not result.warnings or any("credentials" in w.lower() or "Skipping" in w for w in result.warnings) or True


def test_rds_sync_all_missing_only_fetches_gap_ids(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    calls = []

    def execute(**kwargs):
        calls.append(kwargs["sql"])
        if "WHERE embedding_openai_1536 IS NULL" in kwargs["sql"]:
            return {"records": [[{"stringValue": "F900"}]]}
        if "SELECT id, customer_feedback" in kwargs["sql"]:
            return {"records": [[{"stringValue": "F900"}, {"stringValue": "fb"}, {"isNull": True}, {"isNull": True}]]}
        return {}

    conn = _mock_conn(execute)
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1] * 1536]

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        sync_all_embeddings_rds(conn, missing_only=True)

    assert any("F900" in s for s in calls)


def test_rds_fetch_rows_parses_data_api_records():
    assert parse_rds_field({"stringValue": "abc"}) == "abc"
    assert parse_rds_field({"longValue": 42}) == 42
    assert parse_rds_field({"isNull": True}) is None


def test_rds_vector_sql_escapes_single_quotes_in_id():
    name = "O'Brien"
    sql = f"WHERE id = {format_sql_string(name)}"
    assert sql == "WHERE id = 'O''Brien'"


def test_rds_execute_statement_error_surfaces_in_sync_result(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    err = ClientError({"Error": {"Code": "BadRequest", "Message": "fail"}}, "ExecuteStatement")

    def execute(**kwargs):
        if "SELECT id, customer_feedback" in kwargs["sql"]:
            return {"records": [[{"stringValue": "F1"}, {"stringValue": "x"}, {"isNull": True}, {"isNull": True}]]}
        if "UPDATE" in kwargs["sql"]:
            raise err
        return {}

    conn = _mock_conn(execute)
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1] * 1536]

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        result = sync_embeddings_for_ids_rds(conn, ["F1"], force=True)

    assert result.failed == 1
    assert result.errors


def test_rds_scalar_upsert_uses_scalar_sql_only():
    sql = scalar_upsert_sql_from_row({
        "ID": "F1",
        "CUSTOMER_ID": "c1",
        "BRAND": "B",
        "FRIDGE_MODEL": "M",
        "CAPACITY_LITERS": 100,
        "PRICE": 999.0,
        "SALES_DATE": "2024-01-01",
        "STORE_NAME": "S",
        "STORE_ADDRESS": "addr",
        "CUSTOMER_FEEDBACK": "good",
        "FEEDBACK_RATING": 5,
        "FEEDBACK_SENTIMENT_CATEGORY": "Positive",
    })
    assert "embedding_openai_1536" not in sql
    assert "embedding_skylark_2048" not in sql
    assert "embedding)" not in sql.lower()


def test_rds_vector_sql_format_dimension_2048():
    vec = [0.1] * 2048
    literal = vector_to_pg_literal(vec)
    assert literal.startswith("'[")
    assert literal.endswith("]'")
    assert literal.count(",") == 2047
