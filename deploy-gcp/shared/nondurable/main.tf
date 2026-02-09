
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "google_storage_bucket" "delta" {
  name          = var.gcs_delta_bucket
  location      = var.gcp_region
  force_destroy = true
  versioning {
    enabled = true
  }
}
