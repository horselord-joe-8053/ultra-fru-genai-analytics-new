# Reference: infra_terraform/live_deploy/aws/scope_shared/durable_with_cooloff/main.tf
# Durable-with-cooloff: Secret Manager secrets only (AWS: Secrets Manager).
# Values set by tools/gcp/ensure_secrets.py (to be implemented).

terraform {
  backend "gcs" {}
  required_version = ">= 1.6.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

module "tags" {
  source = "../../../../modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "shared"
    durability  = "durable_with_cooloff"
  }
}

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "${var.prefix}-${var.env}-openai_api_key-${var.gcp_region}"

  replication {
    auto {}
  }

  labels = module.tags.common_tags
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.prefix}-${var.env}-db_password-${var.gcp_region}"

  replication {
    auto {}
  }

  labels = module.tags.common_tags
}

resource "google_secret_manager_secret" "db_password_plain" {
  secret_id = "${var.prefix}-${var.env}-db_password_plain-${var.gcp_region}"

  replication {
    auto {}
  }

  labels = module.tags.common_tags
}

resource "google_secret_manager_secret" "google_ai_api_key" {
  secret_id = "${var.prefix}-${var.env}-google_ai_api_key-${var.gcp_region}"

  replication {
    auto {}
  }

  labels = module.tags.common_tags
}

resource "google_secret_manager_secret" "claude_api_key" {
  secret_id = "${var.prefix}-${var.env}-claude_api_key-${var.gcp_region}"

  replication {
    auto {}
  }

  labels = module.tags.common_tags
}

output "openai_api_key_secret_id"   { value = google_secret_manager_secret.openai_api_key.secret_id }
output "google_ai_api_key_secret_id" { value = google_secret_manager_secret.google_ai_api_key.secret_id }
output "claude_api_key_secret_id"   { value = google_secret_manager_secret.claude_api_key.secret_id }
output "db_password_secret_id" { value = google_secret_manager_secret.db_password.secret_id }
output "db_password_plain_secret_id" { value = google_secret_manager_secret.db_password_plain.secret_id }
