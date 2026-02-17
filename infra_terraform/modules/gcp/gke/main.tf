# GCP GKE Cluster Module
# Minimal GKE cluster for phase-1 parity

resource "google_container_cluster" "main" {
  name               = var.cluster_name
  location           = var.location
  initial_node_count = var.initial_node_count
}
