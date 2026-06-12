"""
SQL generation tool for agent using LLM.

Applicable environment: [local] [aws {ecs | eks}] [azure {aci | aks}] [gcp {cloud-run | gke}]
"""
import time
import logging
import re
from typing import Dict, Any, Optional, Tuple

from .base_tool import BaseTool
from backend.env_utils.cloud_shared.client_factory import claude_complete
from backend.utils.postgresql_sql import normalize_postgresql_sql

logger = logging.getLogger(__name__)


class SQLGeneratorTool(BaseTool):
    """Tool for generating SQL queries from natural language using LLM."""
    
    def __init__(self, llm_client, schema_info: Dict[str, Any]):
        super().__init__(
            name="generate_sql",
            description="Generate SQL SELECT queries from natural language questions. Returns a dict with 'sql' field containing the PostgreSQL SQL query. IMPORTANT: After generating SQL, you MUST call execute_sql with the 'sql' value from this tool's output."
        )
        self.llm_client = llm_client  # Cloud-agnostic; stored for future use; currently uses claude_complete()
        self.schema_info = schema_info
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for SQL generation."""
        schema_desc = self._format_schema_info()
        
        return f"""You are a SQL query generator for a fridge sales analytics database.

Database Schema:
{schema_desc}

Rules:
1. Generate ONLY valid PostgreSQL SELECT queries (database is PostgreSQL, NOT MySQL)
2. NEVER use MySQL-only functions: SUBSTRING_INDEX, IFNULL, GROUP_CONCAT, etc.
3. Use PostgreSQL functions instead: SPLIT_PART, COALESCE, STRING_AGG
4. Use the exact column names from the schema
5. For aggregations, use SUM(price) for revenue, COUNT(*) for counts
6. Location from store_address (see schema): city = TRIM(SPLIT_PART(store_address, ',', 2)); state abbr = TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1)). Index 2 is city, NOT state.
7. Prefer store_address parsing over store_name for city/state geography; store_name is a display label (e.g. "Kansas City Store").
8. For US region buckets, use CASE/LIKE on store_address or parsed city
9. Always include appropriate WHERE clauses for filtering
10. Use GROUP BY for aggregations
11. Use ORDER BY for sorting (DESC for highest/biggest, ASC for lowest/smallest)
12. Return ONLY the SQL query, no explanations or markdown

Example:
Question: "How many Samsung fridges were sold?"
SQL: SELECT COUNT(*) AS total_sales FROM fru_sales_embeddings WHERE brand = 'Samsung';

Question: "Which region has the biggest sales?"
SQL: SELECT 
    CASE 
        WHEN store_address LIKE '%New York%' OR store_address LIKE '%Boston%' THEN 'Northeast'
        WHEN store_address LIKE '%Chicago%' OR store_address LIKE '%Detroit%' THEN 'Midwest'
        WHEN store_address LIKE '%Los Angeles%' OR store_address LIKE '%San Francisco%' THEN 'West'
        WHEN store_address LIKE '%Houston%' OR store_address LIKE '%Miami%' THEN 'South'
        ELSE 'Other'
    END AS region,
    SUM(price) AS total_sales
FROM fru_sales_embeddings
GROUP BY region
ORDER BY total_sales DESC
LIMIT 1;

Question: "Which city has the highest total sales revenue?"
SQL: SELECT TRIM(SPLIT_PART(store_address, ',', 2)) AS city, SUM(price) AS total_sales
FROM fru_sales_embeddings
GROUP BY TRIM(SPLIT_PART(store_address, ',', 2))
ORDER BY total_sales DESC
LIMIT 1;

Question: "Which US state has the highest total sales revenue?"
SQL: SELECT TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1)) AS state_abbr, SUM(price) AS total_sales
FROM fru_sales_embeddings
GROUP BY TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1))
ORDER BY total_sales DESC
LIMIT 1;
"""
    
    def _format_schema_info(self) -> str:
        """Format schema information for prompt."""
        table = self.schema_info.get("table", "fru_sales_embeddings")
        columns = self.schema_info.get("columns", {})
        
        lines = [f"Table: {table}", ""]
        for col_name, col_type in columns.items():
            lines.append(f"  - {col_name}: {col_type}")

        lines.extend([
            "",
            "store_address format (comma-separated, fixed 3-part US mailing layout):",
            '  "<street>, <city>, <ST> <zip>"  e.g. "123 Broadway, New York, NY 10001"',
            "  - Part 1 (index 1): street",
            "  - Part 2 (index 2): city — TRIM(SPLIT_PART(store_address, ',', 2))",
            "  - Part 3 (index 3): state abbr + zip — state is first token:",
            "      TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1))  → NY, MO, CA, …",
            "  - store_name is a label (e.g. \"Kansas City Store\"); use parsed city/state for geography.",
        ])
        
        return "\n".join(lines)
    
    def _extract_sql(self, response: str) -> str:
        """Extract SQL from LLM response."""
        # Remove markdown code blocks if present
        response = response.strip()
        
        # Remove ```sql or ``` markers
        response = re.sub(r'^```sql\s*', '', response, flags=re.MULTILINE)
        response = re.sub(r'^```\s*', '', response, flags=re.MULTILINE)
        response = re.sub(r'```\s*$', '', response, flags=re.MULTILINE)
        
        # Extract SQL (everything between first SELECT and last semicolon)
        sql_match = re.search(r'(SELECT.*?;)', response, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        
        # If no match, return cleaned response
        return response.strip()
    
    def validate_input(self, question: str = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate input question."""
        if not question:
            return False, "question is required"
        
        if len(question.strip()) < 5:
            return False, "question must be at least 5 characters"
        
        return True, None
    
    def execute(self, question: str = None, query: str = None, **kwargs) -> Dict[str, Any]:
        """Generate SQL from natural language. Accepts 'question' or 'query' parameter."""
        # Handle both parameter names
        if question is None and query is not None:
            question = query
        elif question is None:
            return {
                "success": False,
                "error": "Question is required (provide 'question' or 'query' parameter)",
                "execution_time_ms": 0
            }
        
        logger.info(f"[SQLGeneratorTool] ===== SQL GENERATION START =====")
        logger.info(f"[SQLGeneratorTool] Question: '{question}'")
        start_time = time.time()
        
        # Validate input
        is_valid, error_msg = self.validate_input(question=question)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "execution_time_ms": (time.time() - start_time) * 1000
            }
        
        try:
            # Log schema info being used
            logger.info(f"[SQLGeneratorTool] Schema info being used:")
            logger.info(f"[SQLGeneratorTool]   Table: {self.schema_info.get('table', 'N/A')}")
            columns = self.schema_info.get('columns', {})
            logger.info(f"[SQLGeneratorTool]   Available columns ({len(columns)}): {list(columns.keys())}")
            for col_name, col_type in columns.items():
                logger.info(f"[SQLGeneratorTool]     - {col_name}: {col_type}")
            
            system_prompt = self._build_system_prompt()
            user_message = f"Generate a SQL query for this question: {question}"
            
            # Log prompts being sent (truncated for readability)
            logger.debug(f"[SQLGeneratorTool] System prompt (first 500 chars): {system_prompt[:500]}...")
            logger.debug(f"[SQLGeneratorTool] User message: {user_message}")
            
            # Call Claude
            logger.info(f"[SQLGeneratorTool] Calling LLM to generate SQL...")
            response_result = claude_complete(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=500
            )
            
            # Handle both dict (new format) and str (backward compatibility)
            if isinstance(response_result, dict):
                response = response_result.get("text", "")
                tokens = response_result.get("tokens", {})
                if tokens.get("total", 0) > 0:
                    logger.debug(f"[SQLGeneratorTool] Token usage: input={tokens.get('input', 0)}, output={tokens.get('output', 0)}, total={tokens.get('total', 0)}")
            else:
                response = response_result
                tokens = {}
            
            logger.info(f"[SQLGeneratorTool] LLM response received: {len(response)} chars")
            logger.info(f"[SQLGeneratorTool] LLM response (full): {response}")
            
            # Extract SQL and normalize MySQL-isms to PostgreSQL
            sql = normalize_postgresql_sql(self._extract_sql(response))
            
            execution_time = (time.time() - start_time) * 1000
            
            logger.info(f"[SQLGeneratorTool] ===== SQL GENERATION SUCCESS =====")
            logger.info(f"[SQLGeneratorTool] Generated SQL (FULL - split across lines):")
            # Log SQL in multiple lines to avoid truncation
            for i, line in enumerate(sql.split('\n'), 1):
                logger.info(f"[SQLGeneratorTool]   Line {i}: {line}")
            logger.info(f"[SQLGeneratorTool] SQL length: {len(sql)} chars")
            logger.info(f"[SQLGeneratorTool] Generation time: {execution_time:.2f}ms")
            
            return {
                "success": True,
                "sql": sql,
                "execution_time_ms": execution_time,
                "tokens": tokens,
            }
        
        except Exception as e:
            error_msg = f"SQL generation failed: {str(e)}"
            logger.error(f"[SQLGeneratorTool] ===== SQL GENERATION FAILED =====")
            logger.error(f"[SQLGeneratorTool] Error: {error_msg}")
            logger.error(f"[SQLGeneratorTool] Question that failed: '{question}'")
            return {
                "success": False,
                "error": error_msg,
                "execution_time_ms": (time.time() - start_time) * 1000
            }

