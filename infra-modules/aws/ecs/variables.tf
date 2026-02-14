variable "name" { type = string }
variable "env" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

variable "cluster_name" { type = string }
variable "alb_name" { type = string }

variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }

variable "container_name" {
  type    = string
  default = "fru-api"
}
variable "container_port" {
  type    = number
  default = 5001
}

variable "app_image" { type = string }

variable "env_vars" {
  type    = map(string)
  default = {}
}

variable "secret_arns" {
  type    = map(string)
  default = {}
}

variable "desired_count" {
  type    = number
  default = 1
}

# Spark schedule
variable "delta_bucket" { type = string }
variable "spark_image" { type = string }
variable "spark_schedule_expression" {
  type    = string
  default = "rate(1 hour)"
}
