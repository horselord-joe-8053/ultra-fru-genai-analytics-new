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

# Durable VPC network/subnetwork so GKE nodes can reach Cloud SQL private IP.
# Auto-mode VPC: subnet in each region has same name as network.
locals {
  durable_network    = data.terraform_remote_state.shared_durable.outputs.network_id
  durable_subnetwork = "projects/${var.gcp_project_id}/regions/${var.gcp_region}/subnetworks/${data.terraform_remote_state.shared_durable.outputs.network_name}"
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
  network             = local.durable_network
  subnetwork          = local.durable_subnetwork
}

# Cloud CDN + GCS frontend (API origin via ingress_hostname when GKE LB is ready)
# CDN gives IP only, HTTP only. Cloud Run proxy (below) provides HTTPS + *.run.app.
module "frontend" {
  source = "../../../modules/gcp/primitives/cloud_cdn"
  prefix = var.prefix
  env    = var.env
  suffix = "kube"

  gcp_region          = var.gcp_region
  gcp_project_id      = var.gcp_project_id
  tags                = module.tags.common_tags
  api_origin_hostname = var.ingress_hostname
}

# Cloud Run proxy: single entry with HTTPS + *.run.app. Routes to GCS (frontend) and GKE LB (API).
# Created only when ingress_hostname is set (after kube_apply creates the LB).
# Grant default compute SA read access to frontend bucket (proxy fetches static from GCS).
data "google_project" "current" { project_id = var.gcp_project_id }
resource "google_storage_bucket_iam_member" "kube_proxy_read_frontend" {
  count  = var.ingress_hostname != null && var.ingress_hostname != "" ? 1 : 0
  bucket = module.frontend.bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}
module "kube_proxy" {
  source   = "../../../modules/gcp/cloud_run"
  count    = var.ingress_hostname != null && var.ingress_hostname != "" ? 1 : 0
  service_name      = "${var.prefix}-api-kube-${var.env}-${var.gcp_region}"
  location          = var.gcp_region
  project_id        = var.gcp_project_id
  image             = "${try(data.terraform_remote_state.shared_nondurable.outputs.artifact_registry_app_url, "")}/kube-proxy:${var.kube_proxy_image_tag}"
  vpc_connector_id  = null
  env_vars = {
    GKE_LB_URL   = "http://${var.ingress_hostname}"
    GCS_BUCKET   = module.frontend.bucket_name
    GCP_PROJECT  = var.gcp_project_id
  }
  secret_ids        = {}
  min_instance_count = 0
  max_instance_count = 2
  allow_unauthenticated = true
  depends_on = [google_storage_bucket_iam_member.kube_proxy_read_frontend]
}

output "gke_cluster_name" { value = module.gke.cluster_name }
output "gke_cluster_endpoint" { value = module.gke.cluster_endpoint }
output "cloudfront_domain_name" { value = module.frontend.cdn_domain_name }
output "frontend_bucket_name" { value = module.frontend.bucket_name }
output "url_map_name" { value = module.frontend.url_map_name }
# Cloud Run proxy URL (HTTPS + *.run.app). Primary user-facing URL for kube.
output "kube_base_url" {
  value = length(module.kube_proxy) > 0 ? module.kube_proxy[0].service_url : null
}
output "artifact_registry_app_url" { value = try(data.terraform_remote_state.shared_nondurable.outputs.artifact_registry_app_url, "") }
output "artifact_registry_spark_url" { value = try(data.terraform_remote_state.shared_nondurable.outputs.artifact_registry_spark_url, "") }
output "delta_bucket" { value = try(data.terraform_remote_state.shared_nondurable.outputs.delta_bucket_name, "") }
