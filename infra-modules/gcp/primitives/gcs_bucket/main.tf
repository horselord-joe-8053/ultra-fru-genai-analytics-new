# GCP Cloud Storage Bucket Module - Placeholder
# TODO: Implement GCS bucket creation
# Reference: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket

resource "google_storage_bucket" "this" {
  name          = var.name
  location      = "US"  # TODO: Make configurable
  force_destroy = false

  labels = var.tags

  # TODO: Add versioning, encryption, lifecycle policies as needed
}
