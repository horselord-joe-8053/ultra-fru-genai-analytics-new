variable "prefix" { type = string }
variable "env" { type = string }
variable "gcp_project_id" { type = string }
variable "gcp_region" { type = string }
variable "tf_state_bucket" { type = string }
variable "tf_state_prefix" { type = string }

variable "cloud_sql_database_name" {
  type    = string
  default = "fru_db"
}
variable "cloud_sql_root_password" {
  type      = string
  sensitive = true
}
variable "cloud_sql_tier" {
  type    = string
  default = "db-f1-micro"
}
variable "cloud_sql_deletion_protection" {
  type    = bool
  default = false
}

# Placeholder image for db-setup job; setup_database.py updates via gcloud deploy.
variable "db_setup_job_image" {
  type    = string
  default = "gcr.io/google-samples/hello-app:1.0"
}
