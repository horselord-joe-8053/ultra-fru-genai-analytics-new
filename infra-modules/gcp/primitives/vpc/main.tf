# GCP VPC Module - Placeholder
# TODO: Implement VPC and subnet creation
# Reference: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_network

resource "google_compute_network" "this" {
  name                    = var.name
  auto_create_subnetworks = false

  # TODO: Add firewall rules, routing as needed
}

# TODO: Add subnet resources
# TODO: Add NAT gateway if enabled
# TODO: Add Cloud Router if NAT is enabled
