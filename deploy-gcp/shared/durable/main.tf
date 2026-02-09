
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

resource "google_compute_network" "vpc" {
  name                    = "${var.prefix}-${var.env}-net"
  auto_create_subnetworks = true
}
