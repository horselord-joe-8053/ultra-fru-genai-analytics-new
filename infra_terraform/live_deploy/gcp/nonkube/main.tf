# Reference: infra_terraform/live_deploy/aws/nonkube/main.tf
# AWS: ECS + CloudFront + remote state. GCP: Cloud Run + Cloud CDN + Cloud Run Jobs (Spark) + remote state.

terraform {
  backend "gcs" {}
  required_version = ">= 1.6.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

data "terraform_remote_state" "shared_durable" {
  backend = "gcs"
  config = {
    bucket = var.tf_state_bucket
    prefix = "${var.tf_state_prefix}/${var.env}/${var.gcp_region}/gcp-shared-durable.tfstate"
  }
}

data "terraform_remote_state" "shared_nondurable" {
  backend = "gcs"
  config = {
    bucket = var.tf_state_bucket
    prefix = "${var.tf_state_prefix}/${var.env}/${var.gcp_region}/gcp-shared-nondurable.tfstate"
  }
}

module "tags" {
  source = "../../../modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "nonkube"
    durability  = "nondurable"
  }
}

locals {
  delta_bucket = try(data.terraform_remote_state.shared_nondurable.outputs.delta_bucket_name, var.delta_bucket_fallback)
  cloud_sql_connection = (try(data.terraform_remote_state.shared_durable.outputs.cloud_sql_private_ip, "") != "" || try(data.terraform_remote_state.shared_durable.outputs.cloud_sql_connection_name, "") != "") ? {
    PGHOST     = try(data.terraform_remote_state.shared_durable.outputs.cloud_sql_private_ip, "")
    PGPORT     = "5432"
    PGDATABASE = try(data.terraform_remote_state.shared_durable.outputs.cloud_sql_database_name, "fru_db")
    PGUSER     = "postgres"
  } : {}
  secret_ids = {
    OPENAI_API_KEY     = try(data.terraform_remote_state.shared_durable.outputs.openai_api_key_secret_id, "")
    PGPASSWORD         = try(data.terraform_remote_state.shared_durable.outputs.db_password_plain_secret_id, "")
    GOOGLE_AI_API_KEY  = try(data.terraform_remote_state.shared_durable.outputs.google_ai_api_key_secret_id, "")
    CLAUDE_API_KEY     = try(data.terraform_remote_state.shared_durable.outputs.claude_api_key_secret_id, "")
  }
}

module "cloud_run" {
  source = "../../../modules/gcp/cloud_run"

  service_name      = var.cloud_run_service_name
  location          = var.gcp_region
  project_id       = var.gcp_project_id
  image            = var.app_image
  vpc_connector_id = try(data.terraform_remote_state.shared_durable.outputs.vpc_connector_id, null)

  env_vars = merge({
    DEPLOY_SCOPE                          = "nonkube"
    CLOUD_PROVIDER                        = "gcp"
    GCP_LLM_PROVIDER                     = var.llm_provider
    LLM_PROVIDER                         = var.llm_provider
    CLAUDE_MODEL                         = var.claude_model
    CLOUD_REGION                         = var.gcp_region
    LOG_LEVEL                            = var.log_level
    ALLOWED_ORIGINS                      = var.allowed_origins
    USE_AGENT_QUERY                      = var.use_agent_query
    OPENAI_EMBED_MODEL                   = var.openai_embed_model
    ENABLE_ANALYTICS_SCHEDULER           = var.enable_analytics_scheduler
    ANALYTICS_SCHEDULER_INTERVAL_SECONDS = tostring(var.analytics_scheduler_interval_seconds)
    DELTA_TABLE_PATH                     = "gs://${local.delta_bucket}/delta/fru_sales"
    DELTA_LAKE_PACKAGE                   = var.delta_lake_package
    SPARK_HOME                           = var.spark_home
    CONTAINER_TYPE                       = "cloud_run"
    CONTAINER_IMAGE                      = var.app_image
    CONTAINER_IMAGE_TAGS                 = var.app_image_tags
  }, local.cloud_sql_connection)

  secret_ids             = { for k, v in local.secret_ids : k => v if v != "" }
  min_instance_count     = var.min_instance_count
  max_instance_count     = var.max_instance_count
  allow_unauthenticated  = true
}

# Single Spark job: scheduled (Cloud Scheduler) + one-off bootstrap (deploy runs gcloud run jobs execute).
# DRY: one job, two invocation modes. Bootstrap populates batch_analytics immediately after deploy.
module "spark_job" {
  source = "../../../modules/gcp/cloud_run_job"

  job_name   = var.spark_job_name
  location   = var.gcp_region
  project_id = var.gcp_project_id
  image      = var.spark_image

  vpc_connector_id = try(data.terraform_remote_state.shared_durable.outputs.vpc_connector_id, null)

  command = [
    "/opt/spark/bin/spark-submit",
    "--packages", "io.delta:delta-spark_2.13:4.0.0,io.delta:delta-storage:4.0.0,org.apache.hadoop:hadoop-aws:3.3.4",
    "--jars", "/opt/fru/jars/gcs-connector-hadoop3-2.2.7-shaded.jar",
    "/opt/fru/jobs/run_analytics.py"
  ]

  env_vars = merge({
    CLOUD_PROVIDER    = "gcp"
    DEPLOY_SCOPE      = "nonkube"
    SPARK_EXTRA_CONF  = "spark.fru.delta_root=gs://${local.delta_bucket}/delta"
    DELTA_TABLE_PATH  = "gs://${local.delta_bucket}/delta/fru_sales"
  }, local.cloud_sql_connection)

  secret_ids = local.secret_ids["PGPASSWORD"] != "" ? { PGPASSWORD = local.secret_ids["PGPASSWORD"] } : {}
  schedule   = var.spark_schedule_expression
}

module "frontend" {
  source = "../../../modules/gcp/primitives/cloud_cdn"
  prefix = var.prefix
  env    = var.env
  suffix = "nonkube"

  gcp_region              = var.gcp_region
  gcp_project_id          = var.gcp_project_id
  tags                    = module.tags.common_tags
  cloud_run_service_name  = module.cloud_run.service_name
}

output "cloud_run_url" { value = module.cloud_run.service_url }
output "cloud_run_service_name" { value = module.cloud_run.service_name }
output "spark_job_name" { value = module.spark_job.job_name }
output "cloudfront_domain_name" { value = module.frontend.cdn_domain_name }
output "frontend_bucket_name" { value = module.frontend.bucket_name }
output "url_map_name" { value = module.frontend.url_map_name }
