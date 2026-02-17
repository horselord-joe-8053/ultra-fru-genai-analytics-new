
variable "env" { type = string }
variable "prefix" { type = string }
variable "aws_region" { type = string }

variable "ecs_cluster_name" { type = string }
variable "alb_name" { type = string }

variable "app_image" { type = string }
variable "app_image_tags" {
  type    = string
  default = ""
  description = "Comma-separated tags for /version endpoint (e.g. fru_dev_...,latest)"
}
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
variable "delta_lake_package" {
  type    = string
  default = "io.delta:delta-spark_2.13:4.0.0"
}
variable "spark_home" {
  type    = string
  default = "/opt/spark"
}
variable "bedrock_inference_profile_id" {
  type    = string
  default = ""
}
variable "bedrock_model_id" {
  type    = string
  default = "anthropic.claude-3-5-haiku-20241022-v1:0"
}

variable "tf_state_bucket" { type = string }
variable "tf_state_prefix" { type = string }

variable "cloudfront_price_class" {
  type    = string
  default = "PriceClass_100"
}
variable "certificate_arn" {
  type    = string
  default = null
}
