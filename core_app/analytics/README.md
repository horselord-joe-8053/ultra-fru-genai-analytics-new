# Analytics (Spark + Delta)

Canonical batch pipeline: read `fru_sales_raw` (PostgreSQL), materialize **Delta** tables, compute aggregates, write **`batch_analytics`** for the UI `/analytics` endpoint.

## Flow

1. **Bootstrap** after deploy — prefill dashboards (K8s Job, ECS/Cloud Run one-off, or local `docker run`)
2. **Recurring schedule** — K8s CronJob (kube), EventBridge/Cloud Scheduler (nonkube), or `tools/local/scheduler_local.py` (local)
3. **Same job code** — `core_app/analytics/jobs/run_analytics.py` in the Spark image for all providers/scopes

See [docs/learned/cloud_shared/ANALYTICS_AND_DATA.md](../../docs/learned/cloud_shared/ANALYTICS_AND_DATA.md).

## Delta paths (dev dual-scope)

In **dev**, kube and nonkube may run in the same account. Delta URIs are **per deploy scope** so concurrent Spark jobs do not overwrite one table:

- Resolver: `tools/cloud_shared/delta_paths.py` (`s3a://…/delta/{scope}/fru_sales`, `gs://…/delta/{scope}/fru_sales`)
- Env: `DELTA_TABLE_PATH` + `DEPLOY_SCOPE` on API and Spark manifests
- Local nonkube: `file:///tmp/delta/fru_sales` (shared Docker volume `fru_delta`)

`run_analytics.py` retries Delta **overwrite** on `ConcurrentAppend` / `DELTA_CONCURRENT_APPEND` (local overlap safety net).

## Run status (`analytics_run_status`)

Spark jobs upsert a singleton row (`last_attempt_at`, `last_success_at`, `last_error`, `deploy_scope`) so the **Batch Analytics** panel can show scheduler history. Implemented in:

- `tools/cloud_shared/analytics_run_status.py` (orchestrator / local scheduler)
- `core_app/analytics/jobs/utils/save_to_db.py` (Spark image, no backend deps)

## Local scheduler

`tools/local/scheduler_local.py` — loops on `ANALYTICS_SCHEDULER_INTERVAL_SECONDS` when `ENABLE_ANALYTICS_SCHEDULER=true`, invoking `docker run fru-spark:local … run_analytics.py`. Started by `tools/local/start_local.py` after nonkube deploy.

> **Note:** War story 11 documents a planned Compose `analytics-worker` replacement; current code still uses `scheduler_local.py` + `docker run`.

## Image

`core_app/analytics/docker/Dockerfile` — fat Spark image with Delta + cloud storage connectors. Built alongside the API image during deploy.
