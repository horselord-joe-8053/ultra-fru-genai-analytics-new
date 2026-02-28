# Reference: infra_terraform/modules/aws/ecs/main.tf
# GCP Cloud Run API service (ECS equivalent). Supports Secret Manager via secret_ids.

resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.location
  ingress  = "INGRESS_TRAFFIC_ALL"

  # deletion_protection: not supported in google provider ~> 5.0; added in 6.x

  template {
    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    dynamic "vpc_access" {
      for_each = var.vpc_connector_id != null && var.vpc_connector_id != "" ? [1] : []
      content {
        connector = var.vpc_connector_id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }

    containers {
      image = var.image

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_ids
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = "projects/${var.project_id}/secrets/${env.value}"
              version = "latest"
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
