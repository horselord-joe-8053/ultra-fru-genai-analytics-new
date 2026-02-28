# infra_terraform/live_deploy/gcp/nonkube

**Reference:** `infra_terraform/live_deploy/aws/nonkube/main.tf`

AWS nonkube: ECS module (cluster, ALB, API service, Spark schedule) + CloudFront + S3 frontend + remote state (shared_durable, shared_nondurable).

GCP nonkube (to implement): Cloud Run (API) + Cloud Run Jobs (Spark) + Cloud Scheduler + Cloud Storage + Load Balancer + Cloud CDN + remote state.

Phase-1: Create `main.tf` mirroring AWS structure with GCP equivalents.
