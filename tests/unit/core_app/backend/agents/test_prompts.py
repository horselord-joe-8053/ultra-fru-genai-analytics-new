from backend.agents.prompts import get_agent_system_prompt


def test_get_agent_system_prompt_includes_tools():
    tools = [{"name": "execute_sql", "description": "run sql"}]
    prompt = get_agent_system_prompt(tools)
    assert "execute_sql" in prompt
    assert "fru_sales_embeddings" in prompt
