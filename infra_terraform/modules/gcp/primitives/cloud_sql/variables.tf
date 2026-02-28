variable "instance_name" { type = string }
variable "region" { type = string }
variable "database_name" { type = string }
variable "network_id" { type = string }
variable "root_password" {
  type      = string
  sensitive = true
}
variable "tier" {
  type    = string
  default = "db-f1-micro"
}
variable "deletion_protection" {
  type    = bool
  default = false
}
