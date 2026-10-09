from unittest.mock import MagicMock

import pytest

from backend.agents.tools.sql_generator_tool import SQLGeneratorTool


@pytest.fixture
def sql_generator():
    return SQLGeneratorTool(MagicMock(), {"table": "fru_sales_embeddings", "columns": {}})


def test_schema_prompt_documents_store_address_city_and_state(sql_generator):
    prompt = sql_generator._build_system_prompt()
    assert "store_address format" in prompt
    assert "SPLIT_PART(store_address, ',', 2)" in prompt
    assert "state_abbr" in prompt
    assert "Index 2 is city, NOT state" in prompt


def test_generator_normalizes_substring_index(sql_generator, monkeypatch):
    mysql_sql = (
        "SELECT SUBSTRING_INDEX(store_address, ',', 2) AS city, SUM(price) AS total "
        "FROM fru_sales_embeddings GROUP BY city ORDER BY total DESC LIMIT 1;"
    )

    sql_generator.llm_client.complete = MagicMock(
        return_value={"text": mysql_sql, "tokens": {}}
    )

    out = sql_generator.execute(question="Which city has the highest sales?")
    assert out["success"] is True
    assert "SUBSTRING_INDEX" not in out["sql"].upper()
    assert "SPLIT_PART" in out["sql"].upper()
