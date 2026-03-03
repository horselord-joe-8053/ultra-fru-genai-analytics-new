variable "prefix" { type = string }
variable "env" { type = string }
variable "suffix" { type = string }
variable "gcp_region" { type = string }
variable "gcp_project_id" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
# Cloud Run service name for API origin (/query, /analytics, etc). Null = static only.
# Used for nonkube scope.
variable "cloud_run_service_name" {
  type    = string
  default = null
}

# GKE LoadBalancer hostname or IP for API origin. Used for kube scope when API runs on GKE.
# GKE often exposes only IP; Cloud CDN supports both via INTERNET_FQDN_PORT (hostname) or INTERNET_IP_PORT (IP).
# Mutually exclusive with cloud_run_service_name. Nonkube uses Cloud Run; kube uses GKE LB.
variable "api_origin_hostname" {
  type    = string
  default = null
}
