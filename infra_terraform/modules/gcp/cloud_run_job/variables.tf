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
variable "schedule" { type = string }
variable "max_retries" {
  type    = number
  default = 1
}
variable "timeout" {
  type    = string
  default = "3600s"
}
