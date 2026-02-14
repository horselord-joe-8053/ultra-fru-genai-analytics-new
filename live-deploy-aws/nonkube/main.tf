
terraform {
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

data "terraform_remote_state" "shared_durable" {
  backend = "s3"
  config = {
    bucket       = var.tf_state_bucket
    key          = "${var.tf_state_prefix}/${var.env}/aws-shared-durable.tfstate"
    region       = var.aws_region
    encrypt      = true
    use_lockfile = true
  }
}

data "terraform_remote_state" "shared_nondurable" {
  backend = "s3"
  config = {
    bucket       = var.tf_state_bucket
    key          = "${var.tf_state_prefix}/${var.env}/aws-shared-nondurable.tfstate"
    region       = var.aws_region
    encrypt      = true
    use_lockfile = true
  }
}

module "tags" {
  source = "../../infra-modules/shared/primitives/tags"
  extra_tags = {
    Project     = "FRU-GenAI"
    ManagedBy   = "OpenTofu/Terraform"
    Environment = var.env
    scope       = "nonkube"
    durability  = "nondurable"
  }
}

module "ecs" {
  source = "../../infra-modules/aws/ecs"
  name   = var.prefix
  env    = var.env

  cluster_name = var.ecs_cluster_name
  alb_name     = var.alb_name

  vpc_id             = data.terraform_remote_state.shared_durable.outputs.vpc_id
  public_subnet_ids  = data.terraform_remote_state.shared_durable.outputs.public_subnet_ids
  private_subnet_ids = data.terraform_remote_state.shared_durable.outputs.private_subnet_ids

  app_image     = var.app_image
  desired_count = var.desired_count

  env_vars = {
    AWS_REGION                           = var.aws_region
    LOG_LEVEL                            = var.log_level
    ALLOWED_ORIGINS                      = var.allowed_origins
    USE_AGENT_QUERY                      = var.use_agent_query
    OPENAI_EMBED_MODEL                   = var.openai_embed_model
    ENABLE_ANALYTICS_SCHEDULER           = var.enable_analytics_scheduler
    ANALYTICS_SCHEDULER_INTERVAL_SECONDS = tostring(var.analytics_scheduler_interval_seconds)
    DELTA_TABLE_PATH                     = var.delta_table_path
    CONTAINER_TYPE                       = "ecs"
    CONTAINER_IMAGE                      = var.app_image
  }

  secret_arns = {
    OPENAI_API_KEY = data.terraform_remote_state.shared_durable.outputs.openai_api_key_secret_arn
    PGPASSWORD     = data.terraform_remote_state.shared_durable.outputs.db_password_secret_arn
  }

  delta_bucket             = var.delta_bucket
  spark_image              = var.spark_image
  spark_schedule_expression = var.spark_schedule_expression

  tags = module.tags.common_tags
}

module "frontend" {
  source = "../../infra-modules/aws/primitives/cloudfront"
  prefix = var.prefix
  env    = var.env
  suffix = "nonkube"

  alb_dns_name           = module.ecs.alb_dns_name
  api_origin_id          = "ALB-${var.prefix}-${var.env}-nonkube"
  cloudfront_price_class = var.cloudfront_price_class
  certificate_arn        = var.certificate_arn
  tags                   = module.tags.common_tags
}

output "alb_dns_name" { value = module.ecs.alb_dns_name }
output "ecs_service_name" { value = module.ecs.service_name }
output "ecs_cluster_name" { value = module.ecs.cluster_name }
output "ecs_task_definition_arn" { value = module.ecs.task_definition_arn }
output "ecs_tasks_sg_id" { value = module.ecs.tasks_security_group_id }
output "cloudfront_domain_name" { value = module.frontend.cloudfront_domain_name }
output "cloudfront_distribution_id" { value = module.frontend.cloudfront_distribution_id }
output "frontend_s3_bucket_id" { value = module.frontend.s3_bucket_id }
