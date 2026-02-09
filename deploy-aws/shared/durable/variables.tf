
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
