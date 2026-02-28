# Reference: infra_terraform/modules/aws/primitives/ecr/main.tf
# GCP Artifact Registry for container images (ECR equivalent)

resource "google_artifact_registry_repository" "this" {
  location      = var.location
  repository_id = var.name
  description   = var.description
  format        = "DOCKER"

  labels = var.tags
}
