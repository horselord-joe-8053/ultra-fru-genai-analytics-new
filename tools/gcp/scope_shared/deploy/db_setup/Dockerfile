# Minimal image for GCP Cloud SQL schema + load_data (Cloud Run Job).
# Separate from main app/spark images. Used only for db-setup job.
#
# Build from repo root:
#   docker build -f tools/gcp/scope_shared/deploy/db_setup/Dockerfile -t db-setup:latest .
#
# Contains: Python, psycopg2, pandas, openai, schema, parser, load script, CSV.
# Env: PGHOST, PGPASSWORD, OPENAI_API_KEY, FRU_CSV_PATH, FRU_FORCE_REFRESH_DATA.
FROM python:3.11-slim

RUN pip install --no-cache-dir psycopg2-binary pandas openai

WORKDIR /app

# Schema
COPY core_app/sql/schema_pgvector.sql /app/schema.sql

# Shared logger (info, success, error, step; Heartbeat not used)
COPY tools/__init__.py /app/tools/__init__.py
COPY tools/cloud_shared/__init__.py /app/tools/cloud_shared/__init__.py
COPY tools/cloud_shared/logging/__init__.py /app/tools/cloud_shared/logging/__init__.py
COPY tools/cloud_shared/logging/logger.py /app/tools/cloud_shared/logging/logger.py

# Parse SQL (for db_common.apply_schema) – keep tools structure so import works
COPY tools/cloud_shared/sql/ /app/tools/cloud_shared/sql/

# Shared deploy utils (FORCE_DROP_TABLES for db_common)
COPY tools/cloud_shared/deploy/__init__.py /app/tools/cloud_shared/deploy/__init__.py
COPY tools/cloud_shared/deploy/setup_database_utils.py /app/tools/cloud_shared/deploy/setup_database_utils.py

# Shared DB utilities and scripts
COPY tools/gcp/scope_shared/deploy/db_setup/db_common.py /app/db_common.py
COPY tools/gcp/scope_shared/deploy/db_setup/load.py /app/load.py
COPY tools/gcp/scope_shared/deploy/db_setup/run_schema_and_load.py /app/run_schema_and_load.py
COPY core_app/data/raw/fridge_sales_with_rating.csv /app/data/fridge_sales_with_rating.csv

# Entrypoint: schema + load_data + output FRU_EMBEDDINGS_COUNT
CMD ["python", "/app/run_schema_and_load.py"]
