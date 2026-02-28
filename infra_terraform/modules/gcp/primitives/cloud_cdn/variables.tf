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
variable "cloud_run_service_name" {
  type    = string
  default = null
}
