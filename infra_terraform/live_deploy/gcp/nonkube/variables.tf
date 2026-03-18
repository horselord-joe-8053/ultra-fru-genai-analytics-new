variable "prefix" { type = string }
variable "env" { type = string }
variable "gcp_project_id" { type = string }
variable "gcp_region" { type = string }
variable "cloud_run_service_name" { type = string }
variable "spark_job_name" { type = string }
variable "app_image" { type = string }
variable "spark_image" { type = string }

variable "tf_state_bucket" { type = string }
variable "tf_state_prefix" { type = string }
variable "delta_bucket_fallback" { type = string }

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
variable "llm_provider" {
  type        = string
  default     = "gemini"
  description = "LLM provider for agent: gemini (default) or claude. Use claude to avoid Gemini API quota."
}
variable "claude_model" {
  type        = string
  default     = "claude-3-5-haiku-20241022"
  description = "Claude model ID when GCP_LLM_PROVIDER=claude (e.g. claude-3-5-haiku-20241022, claude-3-5-sonnet-20241022)."
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
variable "app_image_tag" {
  type    = string
  default = ""
  description = "Image tag for /version endpoint (e.g. fru_dev_20260218_abc123)"
}

variable "min_instance_count" {
  type    = number
  default = 0
}
variable "max_instance_count" {
  type    = number
  default = 10
}
variable "spark_schedule_expression" {
  type    = string
  default = "0 * * * *"
}
