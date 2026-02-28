# Reference: infra_terraform/live_deploy/aws/kube/main.tf
# AWS: EKS + remote state (shared_durable, shared_nondurable) + CloudFront + S3 frontend + subnet tags + Aurora ingress
# GCP: GKE + remote state + Cloud CDN + GCS frontend. Cloud SQL ingress when durable has Cloud SQL.

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

data "terraform_remote_state" "shared_durable" {
  backend = "gcs"
  config = {
    bucket = var.tf_state_bucket
    prefix = "${var.tf_state_prefix}/${var.env}/${var.gcp_region}/gcp-shared-durable.tfstate"
  }
}

data "terraform_remote_state" "shared_nondurable" {
  backend = "gcs"
  config = {
    bucket = var.tf_state_bucket
    prefix = "${var.tf_state_prefix}/${var.env}/${var.gcp_region}/gcp-shared-nondurable.tfstate"
  }
}

module "tags" {
  source = "../../../modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "kube"
    durability  = "nondurable"
  }
}

module "gke" {
  source = "../../../modules/gcp/gke"

  cluster_name        = var.gke_cluster_name
  location            = var.gke_location
  initial_node_count  = var.initial_node_count
  deletion_protection = var.gke_deletion_protection
}

# Cloud CDN + GCS frontend (API origin via ingress_hostname when LB is ready)
module "frontend" {
  source = "../../../modules/gcp/primitives/cloud_cdn"
  prefix = var.prefix
  env    = var.env
  suffix  = "kube"

  gcp_region     = var.gcp_region
  gcp_project_id = var.gcp_project_id
  tags           = module.tags.common_tags
}

output "gke_cluster_name" { value = module.gke.cluster_name }
output "gke_cluster_endpoint" { value = module.gke.cluster_endpoint }
output "cloudfront_domain_name" { value = module.frontend.cdn_domain_name }
output "frontend_bucket_name" { value = module.frontend.bucket_name }
output "artifact_registry_app_url" { value = try(data.terraform_remote_state.shared_nondurable.outputs.artifact_registry_app_url, "") }
output "artifact_registry_spark_url" { value = try(data.terraform_remote_state.shared_nondurable.outputs.artifact_registry_spark_url, "") }
output "delta_bucket" { value = try(data.terraform_remote_state.shared_nondurable.outputs.delta_bucket_name, "") }
