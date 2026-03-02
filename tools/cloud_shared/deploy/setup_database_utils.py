"""
Shared utilities for setup_database (AWS Aurora, GCP Cloud SQL).
DRY: schema paths, parse logic, table names for force-refresh.
"""
import os
import subprocess
import sys

# Table names dropped on --force-refresh-data (order matters for FK)
FORCE_DROP_TABLES = ["batch_analytics", "fru_sales_embeddings"]


def get_repo_root() -> str:
    """Repo root (3 levels up from tools/cloud_shared/deploy/)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def get_schema_file_path() -> str:
    """Path to schema_pgvector.sql."""
    return os.path.join(get_repo_root(), "core_app", "sql", "schema_pgvector.sql")


def get_parse_sql_path() -> str:
    """Path to parse_sql_statements.py."""
    return os.path.join(get_repo_root(), "tools", "cloud_shared", "sql", "parse_sql_statements.py")


def get_etl_script_path() -> str:
    """Path to ETL script (AWS: RDS API; GCP may use pg variant)."""
    return os.path.join(get_repo_root(), "core_app", "backend", "etl", "load_openai_embeddings_to_pgvector_rds_api.py")


def get_csv_path() -> str:
    """Path to raw CSV for embeddings."""
    return os.path.join(get_repo_root(), "core_app", "data", "raw", "fridge_sales_with_rating.csv")


def parse_schema_statements(schema_file: str | None = None) -> list[str]:
    """
    Parse schema file into individual SQL statements.
    Uses tools/cloud_shared/sql/parse_sql_statements.py.
    """
    path = schema_file or get_schema_file_path()
    parse_script = get_parse_sql_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Schema file not found: {path}")
    if not os.path.exists(parse_script):
        raise FileNotFoundError(f"parse_sql_statements.py not found: {parse_script}")

    result = subprocess.run(
        [sys.executable, parse_script, path],
        capture_output=True,
        text=True,
        cwd=get_repo_root(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to parse schema: {result.stderr}")

    return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
