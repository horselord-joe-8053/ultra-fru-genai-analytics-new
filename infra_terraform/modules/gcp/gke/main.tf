# GCP GKE Cluster Module (reference: infra_terraform/modules/aws/eks/main.tf)
# GKE cluster; optional network for shared VPC (pass network/subnetwork when available)

resource "google_container_cluster" "main" {
  name                   = var.cluster_name
  location               = var.location
  initial_node_count     = var.initial_node_count
  deletion_protection    = var.deletion_protection
}
