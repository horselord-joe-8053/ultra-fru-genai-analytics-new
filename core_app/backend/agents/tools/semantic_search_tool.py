"""
Semantic search tool for agent using pgvector.

Applicable environment: [local] [aws {ecs | eks}] [azure {aci | aks}] [gcp {cloud-run | gke}]
"""
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import Error as Psycopg2Error
from openai import OpenAI

from backend.env_utils.cloud_shared.embedding_factory import create_embedding_client
from backend.env_utils.cloud_shared.embedding_profiles import (
    get_active_pgvector_column,
    get_active_profile_name,
    get_profiles,
    is_embedding_column,
)
from backend.utils.env_helpers import get_optional_int_env

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# Exec log preview: show top N vector hits with distance + short feedback (not all rows).
TOP_PREVIEW_COUNT = 5
FEEDBACK_SNIPPET_MAX = 72
DEFAULT_SEMANTIC_SEARCH_LIMIT = 25


def default_semantic_search_limit() -> int:
    """Rows fetched from pgvector (override via SEMANTIC_SEARCH_DEFAULT_LIMIT in .env)."""
    return max(1, min(get_optional_int_env("SEMANTIC_SEARCH_DEFAULT_LIMIT", DEFAULT_SEMANTIC_SEARCH_LIMIT), 200))


def _truncate_feedback_snippet(text: str, max_len: int = FEEDBACK_SNIPPET_MAX) -> str:
    """Single-line snippet for execution log (full feedback still in agent rows)."""
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1].rstrip() + "…"


def _build_top_preview(rows: List[Dict[str, Any]], query_text: str) -> Dict[str, Any]:
    """Compact proof-of-search for SSE / Execution Log (top matches only)."""
    matches = []
    for i, row in enumerate(rows[:TOP_PREVIEW_COUNT], start=1):
        dist = row.get("distance")
        matches.append(
            {
                "rank": i,
                "id": (row.get("id") or "").strip(),
                "distance": round(float(dist), 3) if dist is not None else None,
                "store_name": (row.get("store_name") or "").strip(),
                "feedback_snippet": _truncate_feedback_snippet(
                    row.get("customer_feedback")
                ),
            }
        )
    return {"query_text": query_text, "matches": matches}


class SemanticSearchTool(BaseTool):
    """Tool for semantic search using pgvector."""
    
    def __init__(self, db_connection_pool, openai_client: OpenAI, schema_info: Optional[Dict[str, Any]] = None):
        """
        Initialize semantic search tool.
        
        Args:
            db_connection_pool: Database connection pool
            openai_client: OpenAI client for embeddings
            schema_info: Database schema information (optional, for dynamic filter support)
        """
        # Build description dynamically from schema_info if available
        if schema_info and "columns" in schema_info:
            excluded_columns = {c for c in schema_info["columns"] if is_embedding_column(c)}
            excluded_columns.add("id")
            filterable_cols = [
                col for col, col_type in schema_info["columns"].items()
                if col not in excluded_columns and "TEXT" in str(col_type).upper()
            ]
            filter_desc = ", ".join(sorted(filterable_cols)) if filterable_cols else "store_name, brand, feedback_sentiment_category"
        else:
            filter_desc = "store_name, brand, feedback_sentiment_category"
        
        super().__init__(
            name="semantic_search",
            description=f"Search customer feedback using semantic similarity. Can filter by: {filter_desc}."
        )
        self.db_pool = db_connection_pool
        self.openai_client = openai_client
        self.schema_info = schema_info
    
    def _embed_text(self, text: str, embedding_profile: str | None = None) -> List[float]:
        """Generate embedding via active or request-scoped profile."""
        try:
            profile = None
            if embedding_profile:
                profiles = get_profiles()
                profile = profiles.get(embedding_profile)
                if profile is None:
                    raise ValueError(f"Unknown embedding_profile={embedding_profile!r}")
            client = create_embedding_client(profile=profile, openai_client=self.openai_client)
            col = profile.pgvector_column if profile else get_active_pgvector_column()
            prof_name = profile.name if profile else get_active_profile_name()
            logger.info(
                "[SemanticSearchTool] Embedding profile=%s column=%s",
                prof_name,
                col,
            )
            return client.embed_texts([text])[0]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise ValueError(f"Embedding generation failed: {e}")
    
    def validate_input(self, query_text: str = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate search input."""
        if not query_text:
            return False, "query_text is required"
        
        if len(query_text.strip()) < 3:
            return False, "query_text must be at least 3 characters"
        
        return True, None
    
    def execute(
        self,
        query_text: str = None,
        question: str = None,
        query: str = None,
        limit: int | None = None,
        filters: Optional[Dict[str, List[str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute semantic search. Accepts 'query_text', 'question', or 'query' parameter.
        
        Args:
            query_text: Text to search for (or use 'question' or 'query')
            question: Alternative parameter name
            query: Alternative parameter name
            limit: Maximum number of results
            filters: Optional dict with keys: store_name, brand, feedback_sentiment_category
                    Values are lists of strings to filter by
                    Note: feedback_rating is INTEGER (not filterable), use feedback_sentiment_category for sentiment filtering
        
        Returns:
            Dict with success, rows, row_count, error, execution_time_ms
        """
        # Handle multiple parameter names
        if query_text is None:
            if question is not None:
                query_text = question
            elif query is not None:
                query_text = query
            else:
                return {
                    "success": False,
                    "error": "query_text is required (or use 'question' or 'query' parameter)",
                    "execution_time_ms": 0
                }
        
        logger.info(f"[SemanticSearchTool] ===== SEMANTIC SEARCH START =====")
        logger.info(f"[SemanticSearchTool] Query text: '{query_text}'")
        logger.info(f"[SemanticSearchTool] Limit: {limit}, Filters: {filters}")
        embedding_profile = kwargs.get("embedding_profile")
        if limit is None:
            limit = default_semantic_search_limit()
        start_time = time.time()
        
        # Validate input
        is_valid, error_msg = self.validate_input(query_text=query_text)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "execution_time_ms": (time.time() - start_time) * 1000
            }
        
        conn = None
        try:
            # Generate embedding
            logger.info(f"[SemanticSearchTool] Generating embedding for query...")
            embedding = self._embed_text(query_text, embedding_profile=embedding_profile)
            logger.info(f"[SemanticSearchTool] Embedding generated (dimension: {len(embedding)})")
            
            # Build SQL with optional filters + pgvector distance (lower = closer match).
            where_clauses = []
            params = []
            
            # Add filters dynamically based on schema_info
            if filters:
                # Determine which columns are filterable (TEXT columns, excluding id, embedding, and customer_feedback)
                # Note: customer_feedback is the column being searched semantically, not filtered
                filterable_columns = set()
                if self.schema_info and "columns" in self.schema_info:
                    excluded_columns = {
                        c for c in self.schema_info["columns"] if is_embedding_column(c)
                    }
                    excluded_columns.update({"id", "customer_feedback"})
                    for col_name, col_type in self.schema_info["columns"].items():
                        if col_name not in excluded_columns and "TEXT" in str(col_type).upper():
                            filterable_columns.add(col_name)
                else:
                    # Fallback to hardcoded list if schema_info not available
                    # Note: feedback_rating is INTEGER, not filterable; use feedback_sentiment_category instead
                    filterable_columns = {"store_name", "brand", "feedback_sentiment_category"}
                
                # Process each filter dynamically
                for filter_key, filter_values in filters.items():
                    if filter_key in filterable_columns and filter_values:
                        # filter_values should be a list
                        if not isinstance(filter_values, list):
                            filter_values = [filter_values]
                        
                        placeholders = ",".join(["%s"] * len(filter_values))
                        where_clauses.append(f"{filter_key} IN ({placeholders})")
                        params.extend(filter_values)

            embed_col = get_active_pgvector_column()
            if embedding_profile:
                prof = get_profiles().get(embedding_profile)
                if prof:
                    embed_col = prof.pgvector_column
            distance_expr = f"({embed_col} <-> %s::vector)"
            if where_clauses:
                sql = (
                    "SELECT id, brand, fridge_model, price, sales_date, store_name, "
                    "customer_feedback, feedback_rating, feedback_sentiment_category, "
                    f"{distance_expr} AS distance "
                    "FROM fru_sales_embeddings "
                    "WHERE " + " AND ".join(where_clauses) + " "
                )
            else:
                sql = (
                    "SELECT id, brand, fridge_model, price, sales_date, store_name, "
                    "customer_feedback, feedback_rating, feedback_sentiment_category, "
                    f"{distance_expr} AS distance "
                    "FROM fru_sales_embeddings "
                )
            sql += f"ORDER BY {distance_expr} LIMIT %s;"
            params.extend([embedding, embedding, limit])
            
            logger.info(f"[SemanticSearchTool] SQL query: {sql[:200]}...")
            logger.info(f"[SemanticSearchTool] Executing semantic search...")
            
            # Execute query
            conn = self.db_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                result_rows = [dict(row) for row in rows]
                
                execution_time = (time.time() - start_time) * 1000
                
                logger.info(f"[SemanticSearchTool] ===== SEMANTIC SEARCH SUCCESS =====")
                logger.info(f"[SemanticSearchTool] Rows returned: {len(result_rows)}")
                logger.info(f"[SemanticSearchTool] Execution time: {execution_time:.2f}ms")
                if len(result_rows) > 0:
                    logger.info(f"[SemanticSearchTool] First result: {result_rows[0]}")
                
                logger.info(f"Semantic search completed: {len(result_rows)} results in {execution_time:.2f}ms")
                
                return {
                    "success": True,
                    "rows": result_rows,
                    "row_count": len(result_rows),
                    "top_preview": _build_top_preview(result_rows, query_text),
                    "execution_time_ms": execution_time
                }
        
        except Psycopg2Error as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(f"Semantic search error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "execution_time_ms": (time.time() - start_time) * 1000
            }
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"[SemanticSearchTool] ===== SEMANTIC SEARCH FAILED =====")
            logger.error(f"[SemanticSearchTool] Error: {error_msg}")
            logger.error(f"[SemanticSearchTool] Query text that failed: '{query_text}'")
            return {
                "success": False,
                "error": error_msg,
                "execution_time_ms": (time.time() - start_time) * 1000
            }
        
        finally:
            if conn:
                self.db_pool.putconn(conn)

