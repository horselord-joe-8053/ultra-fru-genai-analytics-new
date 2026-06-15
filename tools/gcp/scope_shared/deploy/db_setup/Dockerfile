# Minimal image for GCP Cloud SQL schema + load_data (Cloud Run Job).
# Separate from main app/spark images. Used only for db-setup job.
#
# Build from repo root:
#   docker build -f tools/gcp/scope_shared/deploy/db_setup/Dockerfile -t db-setup:latest .
#
# Contains: backend embedding_sync, schema, load script, CSV.
# Env: PGHOST, PGPASSWORD, OPENAI_API_KEY, ARK_* (from deploy host), FRU_CSV_PATH.
FROM python:3.11-slim

COPY core_app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
ENV PYTHONPATH=/app

# Backend + profile config (dual-profile embedding_sync)
COPY core_app/backend /app/backend
COPY config /app/config

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
