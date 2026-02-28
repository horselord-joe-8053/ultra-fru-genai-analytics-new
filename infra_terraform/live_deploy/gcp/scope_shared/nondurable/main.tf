# Reference: infra_terraform/live_deploy/aws/scope_shared/nondurable/main.tf
# AWS: delta + artifacts buckets, ECR. GCP: delta bucket + Artifact Registry (app, spark).

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
    durability  = "nondurable"
  }
}

module "delta_bucket" {
  source = "../../../../modules/gcp/primitives/gcs_bucket"

  name               = var.gcs_delta_bucket
  location           = var.gcp_region
  force_destroy      = true
  versioning_enabled = true
  tags               = module.tags.common_tags
}

module "artifact_registry_app" {
  source = "../../../../modules/gcp/primitives/artifact_registry"
  name   = var.artifact_registry_repo_app
  location = var.gcp_region
  project_id = var.gcp_project_id
  tags   = module.tags.common_tags
}

module "artifact_registry_spark" {
  source = "../../../../modules/gcp/primitives/artifact_registry"
  name   = var.artifact_registry_repo_spark
  location = var.gcp_region
  project_id = var.gcp_project_id
  tags   = module.tags.common_tags
}

output "delta_bucket_name" { value = module.delta_bucket.bucket_name }
output "artifact_registry_app_url" { value = module.artifact_registry_app.repository_url }
output "artifact_registry_spark_url" { value = module.artifact_registry_spark.repository_url }
