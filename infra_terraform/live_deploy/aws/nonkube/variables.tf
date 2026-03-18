
variable "env" { type = string }
variable "prefix" { type = string }
variable "aws_region" { type = string }

variable "ecs_cluster_name" { type = string }
variable "alb_name" { type = string }
variable "cloudwatch_log_group_ecs_api" {
  type    = string
  default = ""
}
variable "cloudwatch_log_group_spark" {
  type    = string
  default = ""
}

variable "app_image" { type = string }
variable "app_image_tag" {
  type    = string
  default = ""
  description = "Image tag for /version endpoint (e.g. fru_dev_20260218_abc123)"
}
variable "spark_image" { type = string }
variable "delta_bucket" { type = string }
variable "spark_schedule_expression" {
  type    = string
  default = "rate(1 hour)"
}

variable "min_instance_count" { type = number }
variable "max_instance_count" { type = number }
variable "api_task_cpu" { type = number }
variable "api_task_memory" { type = number }
variable "spark_task_cpu" { type = number }
variable "spark_task_memory" { type = number }

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
variable "bedrock_region" {
  type        = string
  default     = "us-east-1"
  description = "Bedrock API region (models live here; may differ from aws_region). Default us-east-1 for Anthropic models."
}

variable "tf_state_bucket" { type = string }
variable "tf_state_bucket_region" { type = string }
variable "tf_state_prefix" { type = string }

variable "cloudfront_price_class" {
  type    = string
  default = "PriceClass_100"
}
variable "certificate_arn" {
  type    = string
  default = null
}
