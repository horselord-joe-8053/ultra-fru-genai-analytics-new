
# Analytics (Spark + Delta)

Canonical analytics pipeline semantics:
1. **Bootstrap run** after deploy to prefill UI dashboards
2. **Recurring schedule** after bootstrap
3. Same job code for kube/nonkube

Jobs are containerized Spark.
