variable "name" { type = string }
variable "env" { type = string }
variable "aws_region" {
  type        = string
  description = "AWS region (used for global IAM role names to avoid cross-region teardown conflicts)"
}
variable "tags" {
  type    = map(string)
  default = {}
}

variable "cluster_name" { type = string }
variable "alb_name" { type = string }

# CloudWatch log groups (path-style). When set, use; else fallback to legacy /{prefix}/{env}/...
variable "cloudwatch_log_group_ecs_api" {
  type        = string
  default     = ""
  description = "Full path for ECS API log group (e.g. /fru/ecs-api/dev/us-east-1)"
}
variable "cloudwatch_log_group_spark" {
  type        = string
  default     = ""
  description = "Full path for Spark log group (e.g. /fru/cloud-log-group-spark/dev/us-east-1)"
}

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

variable "min_instance_count" {
  type        = number
  description = "ECS API service minimum instance count"
}
variable "max_instance_count" {
  type        = number
  description = "ECS API service maximum instance count"
}
variable "api_task_cpu" {
  type        = number
  description = "API task CPU units (1024 = 1 vCPU)"
}
variable "api_task_memory" {
  type        = number
  description = "API task memory in MB"
}
variable "spark_task_cpu" {
  type        = number
  description = "Spark task CPU units"
}
variable "spark_task_memory" {
  type        = number
  description = "Spark task memory in MB"
}

# Spark schedule
variable "delta_bucket" { type = string }
variable "spark_image" { type = string }
variable "spark_schedule_expression" {
  type    = string
  default = "rate(1 hour)"
}

# Aurora (optional - when empty, PG* not passed)
variable "aurora_endpoint" {
  type    = string
  default = ""
}
variable "aurora_port" {
  type    = string
  default = "5432"
}
variable "aurora_database_name" {
  type    = string
  default = "fru_db"
}
variable "aurora_security_group_id" {
  type    = string
  default = ""
}
# Plain DB password secret for Spark task (batch_analytics write)
variable "db_password_plain_secret_arn" {
  type    = string
  default = ""
}
