
variable "env" { type = string }
variable "prefix" { type = string }
variable "aws_region" { type = string }

variable "ecs_cluster_name" { type = string }
variable "alb_name" { type = string }

variable "app_image" { type = string }
variable "spark_image" { type = string }
variable "delta_bucket" { type = string }
variable "spark_schedule_expression" {
  type    = string
  default = "rate(1 hour)"
}

variable "desired_count" {
  type    = number
  default = 1
}

# Env map (non-sensitive)
variable "log_level" {
  type    = string
  default = "INFO"
}
variable "allowed_origins" {
  type    = string
  default = "*"
}
variable "use_agent_query" {
  type    = string
  default = "true"
}
variable "openai_embed_model" {
  type    = string
  default = "text-embedding-3-small"
}
variable "enable_analytics_scheduler" {
  type    = string
  default = "true"
}
variable "analytics_scheduler_interval_seconds" {
  type    = number
  default = 180
}
variable "delta_table_path" {
  type    = string
  default = "s3://example/delta/fru_sales"
}

variable "tf_state_bucket" { type = string }
variable "tf_state_prefix" { type = string }
