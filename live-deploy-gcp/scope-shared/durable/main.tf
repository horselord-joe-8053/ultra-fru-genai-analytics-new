
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

module "vpc" {
  source = "../../../infra-modules/gcp/primitives/vpc"

  name                    = "${var.prefix}-${var.env}-net"
  auto_create_subnetworks = true
}

output "network_name" { value = module.vpc.network_name }
output "network_id" { value = module.vpc.network_id }
