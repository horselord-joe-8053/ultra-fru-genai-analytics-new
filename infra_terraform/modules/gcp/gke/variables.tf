variable "cluster_name" { type = string }
variable "location" { type = string }
variable "initial_node_count" {
  type    = number
  default = 1
}
variable "deletion_protection" {
  type    = bool
  default = false
}

# Optional: use durable VPC so GKE nodes can reach Cloud SQL private IP.
# When set, cluster uses this network/subnetwork instead of default.
variable "network" {
  type    = string
  default = null
}
variable "subnetwork" {
  type    = string
  default = null
}