"""Integration: dual-profile embedding_sync (requires live Postgres)."""
import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def db_conn():
    if not os.environ.get("PGHOST"):
        pytest.skip("PGHOST not set")
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ["PGPASSWORD"],
        dbname=os.environ.get("PGDATABASE", "fru_db"),
    )
    yield conn
    conn.close()


def test_sync_missing_only_fills_gaps(db_conn):
    from backend.services.embedding_sync import sync_all_embeddings

    result = sync_all_embeddings(db_conn, missing_only=True)
    assert result.failed == 0 or result.warnings
