# Analytics (Spark + Delta)

Canonical analytics pipeline semantics:
1. **Bootstrap run** after deploy to prefill UI dashboards
2. **Recurring schedule** after bootstrap (Kube: CronJob; Nonkube: EventBridge)
3. Same job code for kube/nonkube

Jobs are containerized Spark. Both scopes share Delta source and `batch_analytics` table.
See `docs/ANALYTICS_KUBE_NONKUBE_SHARED_DATA.md`.
