variable "service_name" { type = string }
variable "location" { type = string }
variable "image" { type = string }
variable "project_id" { type = string }
variable "env_vars" {
  type    = map(string)
  default = {}
}
# secret_ids: map of env var name -> Secret Manager secret_id (e.g. fru-dev-openai_api_key-us-central1)
variable "secret_ids" {
  type    = map(string)
  default = {}
}
variable "min_instance_count" {
  type    = number
  default = 0
}
variable "max_instance_count" {
  type    = number
  default = 10
}
# deletion_protection: not supported in google provider ~> 5.0; add back when upgrading to 6.x
variable "allow_unauthenticated" {
  type    = bool
  default = true
}
# VPC connector ID for Cloud SQL private IP access (e.g. projects/PROJECT/locations/REGION/connectors/NAME)
variable "vpc_connector_id" {
  type    = string
  default = null
}
variable "cpu" {
  type    = string
  default = null
}
variable "memory" {
  type    = string
  default = null
}
