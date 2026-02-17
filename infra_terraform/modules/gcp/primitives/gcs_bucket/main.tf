# GCP Cloud Storage Bucket Module
# Reference: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket

resource "google_storage_bucket" "this" {
  name          = var.name
  location      = var.location
  force_destroy = var.force_destroy

  labels = var.tags

  dynamic "versioning" {
    for_each = var.versioning_enabled ? [1] : []
    content {
      enabled = true
    }
  }
}
