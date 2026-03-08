# Analytics (Spark + Delta)

Canonical analytics pipeline semantics:
1. **Bootstrap run** after deploy to prefill UI dashboards
2. **Recurring schedule** after bootstrap (Kube: CronJob; Nonkube: EventBridge; Local: `tools/local/scheduler_local.py`)
3. Same job code for kube/nonkube/local

Jobs are containerized Spark. Both scopes share Delta source and `batch_analytics` table.
See `docs/learned/cloud_shared/ANALYTICS_AND_DATA.md`.

## Local scheduler (tools/local/scheduler_local.py)

Local-only. Runs every `ANALYTICS_SCHEDULER_INTERVAL_SECONDS` when `ENABLE_ANALYTICS_SCHEDULER=true`.
Invokes `docker run fru-spark:local ... run_analytics.py`. AWS/GCP use CronJob/EventBridge instead.
