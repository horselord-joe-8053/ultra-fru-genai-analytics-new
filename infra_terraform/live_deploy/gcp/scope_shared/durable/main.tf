# Reference: infra_terraform/live_deploy/aws/scope_shared/durable/main.tf
#
# Durable stack: VPC + Cloud SQL PostgreSQL + secret re-exports.
# Same as AWS: VPC + Aurora + secret ARNs.
#
# Why DB in durable (not nondurable):
# - PostgreSQL is required for all scopes (kube, nonkube). Some stack must create it.
# - DB deploy/teardown is slow (minutes). Treating it as durable avoids frequent churn.
# - Nondurable stacks (GCS, ECR/Artifact Registry) tear down quickly; DB does not.
# - Aligns with AWS: Aurora lives in durable, not nondurable.

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

data "google_project" "project" {
  project_id = var.gcp_project_id
}

data "terraform_remote_state" "durable_with_cooloff" {
  backend = "gcs"
  config = {
    bucket = var.tf_state_bucket
    prefix = "${var.tf_state_prefix}/${var.env}/${var.gcp_region}/gcp-shared-durable_with_cooloff.tfstate"
  }
}

module "vpc" {
  source = "../../../../modules/gcp/primitives/vpc"

  name                    = "${var.prefix}-${var.env}-net"
  auto_create_subnetworks = true
}

# Private service connection required for Cloud SQL private IP (NETWORK_NOT_PEERED)
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "${var.prefix}-${var.env}-private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = module.vpc.network_id
}

# Service networking connection for Cloud SQL private IP. Deletion order: Cloud SQL first
# (async delete 5–15+ min), then this connection. Pre-destroy (durable_pre_destroy.py) runs
# targeted Cloud SQL destroy and polls until instance gone before full durable destroy.
resource "google_service_networking_connection" "default" {
  network                 = module.vpc.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

module "cloud_sql" {
  source = "../../../../modules/gcp/primitives/cloud_sql"

  instance_name       = "${var.prefix}-${var.env}-sql"
  region              = var.gcp_region
  database_name       = var.cloud_sql_database_name
  network_id          = "projects/${var.gcp_project_id}/global/networks/${module.vpc.network_name}"
  root_password       = var.cloud_sql_root_password
  tier                = var.cloud_sql_tier
  deletion_protection = var.cloud_sql_deletion_protection

  depends_on = [google_service_networking_connection.default]
}

output "network_name" { value = module.vpc.network_name }
output "network_id" { value = module.vpc.network_id }

# Re-export secret IDs from durable_with_cooloff
output "openai_api_key_secret_id"    { value = try(data.terraform_remote_state.durable_with_cooloff.outputs.openai_api_key_secret_id, "") }
output "db_password_secret_id"       { value = try(data.terraform_remote_state.durable_with_cooloff.outputs.db_password_secret_id, "") }
output "db_password_plain_secret_id" { value = try(data.terraform_remote_state.durable_with_cooloff.outputs.db_password_plain_secret_id, "") }
output "google_ai_api_key_secret_id"  { value = try(data.terraform_remote_state.durable_with_cooloff.outputs.google_ai_api_key_secret_id, "") }
output "claude_api_key_secret_id"    { value = try(data.terraform_remote_state.durable_with_cooloff.outputs.claude_api_key_secret_id, "") }

# Cloud SQL outputs
output "cloud_sql_connection_name" { value = module.cloud_sql.connection_name }
output "cloud_sql_private_ip"      { value = module.cloud_sql.private_ip }
output "cloud_sql_database_name"   { value = module.cloud_sql.database_name }

# Serverless VPC Access connector for Cloud Run to reach Cloud SQL private IP.
# Requires vpcaccess.googleapis.com API. Uses a /28 range (connector requirement).
resource "google_vpc_access_connector" "cloud_run" {
  name          = "${var.prefix}-${var.env}-run-conn"
  region        = var.gcp_region
  network       = module.vpc.network_name
  ip_cidr_range = "10.126.0.0/28"
}

output "vpc_connector_id" { value = google_vpc_access_connector.cloud_run.id }

# Db-setup Cloud Run Job: runs schema (and optionally load_data) for private-IP Cloud SQL.
# Created by Terraform for clean teardown; image updated by setup_database.py (gcloud deploy).
# No scheduler; executed on demand during deploy.
# lifecycle: ignore template changes so Terraform does not revert gcloud updates (real image, env).
resource "google_cloud_run_v2_job" "db_setup" {
  name     = "${var.prefix}-${var.env}-db-setup"
  location = var.gcp_region

  lifecycle {
    ignore_changes = [template, client, client_version]
  }

  template {
    template {
      vpc_access {
        connector = google_vpc_access_connector.cloud_run.id
        egress    = "PRIVATE_RANGES_ONLY"
      }
      containers {
        image = var.db_setup_job_image

        env {
          name  = "PGHOST"
          value = module.cloud_sql.private_ip
        }
        env {
          name  = "PGPORT"
          value = "5432"
        }
        env {
          name  = "PGUSER"
          value = "postgres"
        }
        env {
          name  = "PGDATABASE"
          value = module.cloud_sql.database_name
        }
        dynamic "env" {
          for_each = try(data.terraform_remote_state.durable_with_cooloff.outputs.db_password_plain_secret_id, "") != "" ? [1] : []
          content {
            name = "PGPASSWORD"
            value_source {
              secret_key_ref {
                secret  = "projects/${data.google_project.project.number}/secrets/${data.terraform_remote_state.durable_with_cooloff.outputs.db_password_plain_secret_id}"
                version = "latest"
              }
            }
          }
        }

        command = ["python", "/app/run_schema_and_load.py"]
      }
      max_retries = 0
      timeout     = "300s"
    }
  }
}
