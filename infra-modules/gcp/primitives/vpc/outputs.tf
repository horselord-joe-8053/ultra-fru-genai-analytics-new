# GCP VPC Module - Outputs Placeholder

output "network_name" {
  value = google_compute_network.this.name
}

output "network_id" {
  value = google_compute_network.this.id
}

# TODO: Add subnet outputs, NAT gateway outputs
