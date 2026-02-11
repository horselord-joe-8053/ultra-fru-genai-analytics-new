
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

resource "google_container_cluster" "gke" {
  name               = var.gke_cluster_name
  location           = var.gcp_region
  initial_node_count = 1
}
