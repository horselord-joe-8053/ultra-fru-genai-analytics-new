# GCP VPC Module
# Reference: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_network

resource "google_compute_network" "this" {
  name                    = var.name
  auto_create_subnetworks = var.auto_create_subnetworks

  # TODO: Add firewall rules, routing, custom subnets when auto_create_subnetworks = false
}
