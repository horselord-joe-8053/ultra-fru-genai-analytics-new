# GCP Secret Manager (reference: infra_terraform/live_deploy/aws/scope_shared/durable_with_cooloff - Secrets Manager)
# Values set by tools/gcp/ensure_secrets.py
resource "google_secret_manager_secret" "this" {
  secret_id = var.secret_id

  replication {
    auto {}
  }

  labels = var.labels
}
