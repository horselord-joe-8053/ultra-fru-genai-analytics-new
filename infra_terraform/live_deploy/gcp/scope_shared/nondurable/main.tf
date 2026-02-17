
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

module "delta_bucket" {
  source = "../../../../modules/gcp/primitives/gcs_bucket"

  name               = var.gcs_delta_bucket
  location           = var.gcp_region
  force_destroy      = true
  versioning_enabled = true
}

output "delta_bucket_name" { value = module.delta_bucket.bucket_name }
