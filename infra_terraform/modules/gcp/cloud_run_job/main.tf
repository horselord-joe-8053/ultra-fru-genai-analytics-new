# Reference: ECS Spark task + EventBridge in aws/ecs. GCP: Cloud Run Job + Cloud Scheduler.

resource "google_cloud_run_v2_job" "spark" {
  name     = var.job_name
  location = var.location

  template {
    template {
      dynamic "vpc_access" {
        for_each = var.vpc_connector_id != null && var.vpc_connector_id != "" ? [1] : []
        content {
          connector = var.vpc_connector_id
          egress    = "PRIVATE_RANGES_ONLY"
        }
      }
      containers {
        image = var.image

        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
        }

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

        command = var.command
      }
      max_retries = var.max_retries
      # task_count: not in inner template; default is 1 task per execution
      timeout = var.timeout
    }
  }
}

resource "google_cloud_scheduler_job" "spark" {
  count       = var.schedule != "" ? 1 : 0
  name        = "${var.job_name}-schedule"
  description = "Schedule for ${var.job_name}"
  schedule    = var.schedule
  time_zone   = "UTC"
  region      = var.location

  http_target {
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/${google_cloud_run_v2_job.spark.name}:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
    }
  }
}

resource "google_service_account" "scheduler" {
  count        = var.schedule != "" ? 1 : 0
  account_id   = "${replace(var.job_name, "-", "")}-sched"
  display_name = "Scheduler for ${var.job_name}"
}

resource "google_project_iam_member" "scheduler_run_invoker" {
  count   = var.schedule != "" ? 1 : 0
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.scheduler[0].email}"
}
