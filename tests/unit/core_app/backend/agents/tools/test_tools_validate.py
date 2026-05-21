from unittest.mock import MagicMock

from backend.agents.tools.semantic_search_tool import SemanticSearchTool
from backend.agents.tools.sql_tool import SQLTool
from backend.agents.tools.sql_generator_tool import SQLGeneratorTool


def test_semantic_search_validate_input():
    tool = SemanticSearchTool(db_connection_pool=None, openai_client=MagicMock())
    ok, err = tool.validate_input(query_text="ab")
    assert not ok
    ok, err = tool.validate_input(query_text="hello world")
    assert ok and err is None


def test_sql_tool_blocks_drop():
    tool = SQLTool(db_connection_pool=None)
    ok, err = tool.validate_input(sql_query="DROP TABLE fru_sales_embeddings")
    assert not ok
    assert "DROP" in err


def test_sql_tool_allows_select():
    tool = SQLTool(db_connection_pool=None)
    ok, err = tool.validate_input(sql_query="SELECT count(*) FROM fru_sales_embeddings")
    assert ok and err is None


def test_sql_generator_requires_question():
    tool = SQLGeneratorTool(llm_client=MagicMock(), schema_info={"columns": {}})
    ok, err = tool.validate_input()
    assert not ok
