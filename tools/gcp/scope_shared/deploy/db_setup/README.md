# GCP db_setup (internal to setup_database.py)

Helpers for running schema + load_data via Cloud Run Job when Cloud SQL is private-IP-only.

**Entry point:** `tools/gcp/scope_shared/deploy/setup_database.py` (overlord).

| File | Purpose |
|------|---------|
| `cloud_job.py` | Build, deploy, execute, wait, verify count. run_and_verify() used by deploy + verify_db_run_job |
| `config.py` | Resolve job config from durable Terraform outputs |
| `job_client.py` | gcloud wrappers: create/update job, execute, poll status |
| `db_common.py` | Shared: get_db_config, connect_db, apply_schema |
| `run_schema_and_load.py` | Entrypoint: schema + load_data + FRU_EMBEDDINGS_COUNT output |
| `Dockerfile` | Image: schema + load_data, CSV, pandas, openai |

Idempotent: load_data skips if data exists unless FRU_FORCE_REFRESH_DATA=true.
