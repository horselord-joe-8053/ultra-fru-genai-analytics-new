variable "prefix" { type = string }
variable "env" { type = string }
variable "gcp_project_id" { type = string }
variable "gcp_region" { type = string }
variable "gke_cluster_name" { type = string }
# GKE location: zone (e.g. us-central1-a) for zonal cluster, or region for regional.
variable "gke_location" { type = string }
variable "initial_node_count" {
  type    = number
  default = 1
}
variable "gke_deletion_protection" {
  type    = bool
  default = false
}

variable "tf_state_bucket" { type = string }
variable "tf_state_prefix" { type = string }
