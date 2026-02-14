
variable "prefix" { type = string }
variable "env" { type = string }
variable "aws_region" { type = string }
variable "vpc_cidr" { type = string }
variable "azs" { type = list(string) }
variable "public_subnet_cidrs" { type = list(string) }
variable "private_subnet_cidrs" { type = list(string) }

variable "allow_destroy_durable" {
  type    = bool
  default = false
}
variable "tf_state_bucket" { type = string }
variable "tf_lock_table" { type = string }
variable "tf_state_prefix" { type = string }

# Aurora
variable "aurora_database_name" {
  type    = string
  default = "fru_db"
}
variable "aurora_master_username" {
  type    = string
  default = "postgres"
}
variable "aurora_master_password" {
  type      = string
  sensitive = true
}
variable "aurora_engine_version" {
  type    = string
  default = "16.4"
}
variable "aurora_instance_class" {
  type    = string
  default = "db.serverless"
}
variable "aurora_instance_count" {
  type    = number
  default = 1
}
variable "aurora_min_capacity" {
  type    = number
  default = 0.5
}
variable "aurora_max_capacity" {
  type    = number
  default = 16
}
variable "aurora_deletion_protection" {
  type    = bool
  default = false
}
