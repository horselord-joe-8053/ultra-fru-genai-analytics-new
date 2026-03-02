variable "job_name" { type = string }
variable "location" { type = string }
variable "project_id" { type = string }
variable "image" { type = string }
variable "command" {
  type    = list(string)
  default = []
}
variable "env_vars" {
  type    = map(string)
  default = {}
}
variable "secret_ids" {
  type    = map(string)
  default = {}
}
variable "schedule" {
  type        = string
  default     = ""
  description = "Cron schedule (e.g. '0 * * * *'). Empty = no scheduler (job-only, for bootstrap)."
}
variable "max_retries" {
  type    = number
  default = 1
}
variable "timeout" {
  type    = string
  default = "3600s"
}
variable "cpu" {
  type        = string
  default     = "2"
  description = "CPU count (e.g. 2 for 2 vCPU). Spark needs at least 2 vCPU."
}
variable "memory" {
  type        = string
  default     = "4Gi"
  description = "Memory limit (e.g. 4Gi). Spark needs at least 2Gi."
}
variable "vpc_connector_id" {
  type        = string
  default     = null
  description = "VPC connector ID for Cloud SQL private IP access (e.g. Spark, db-setup)."
}
