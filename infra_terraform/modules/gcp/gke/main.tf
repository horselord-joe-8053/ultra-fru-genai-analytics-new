# GCP GKE Cluster Module (reference: infra_terraform/modules/aws/eks/main.tf)
# GKE cluster; optional network for shared VPC (pass network/subnetwork when available).
# When network/subnetwork are set, nodes run in that VPC and can reach Cloud SQL private IP.

resource "google_container_cluster" "main" {
  name                = var.cluster_name
  location            = var.location
  deletion_protection = var.deletion_protection
  network             = var.network
  subnetwork          = var.subnetwork

  # Use a dedicated node pool (below) so OAuth scopes are explicit.
  remove_default_node_pool = true
  initial_node_count       = 1
}

resource "google_container_node_pool" "primary" {
  name       = "primary"
  location   = var.location
  cluster    = google_container_cluster.main.name
  node_count = var.initial_node_count

  node_config {
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }
}
