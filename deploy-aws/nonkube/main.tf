
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

module "ecs_alb" {
  source = "../../infra-modules/aws/ecs_alb"
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
  }

  secret_arns = {
    OPENAI_API_KEY = data.terraform_remote_state.shared_durable.outputs.openai_api_key_secret_arn
    PGPASSWORD     = data.terraform_remote_state.shared_durable.outputs.db_password_secret_arn
  }

  tags = module.tags.common_tags
}

# ---- Spark scheduled task (EventBridge -> ECS RunTask) ----
resource "aws_cloudwatch_log_group" "spark" {
  name              = "/fru/${var.env}/spark"
  retention_in_days = 14
  tags              = module.tags.common_tags
}

resource "aws_iam_role" "spark_task_exec" {
  name = "${var.prefix}-${var.env}-spark-task-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = module.tags.common_tags
}

resource "aws_iam_role_policy_attachment" "spark_exec_attach" {
  role       = aws_iam_role.spark_task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow Spark task to read/write delta bucket
resource "aws_iam_role_policy" "spark_s3" {
  name = "${var.prefix}-${var.env}-spark-s3"
  role = aws_iam_role.spark_task_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = [
        "arn:aws:s3:::${var.delta_bucket}",
        "arn:aws:s3:::${var.delta_bucket}/*"
      ]
    }]
  })
}

resource "aws_ecs_task_definition" "spark" {
  family                   = "${var.prefix}-${var.env}-spark"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.spark_task_exec.arn
  container_definitions = jsonencode([{
    name      = "spark"
    image     = var.spark_image
    essential = true
    command   = ["spark-submit", "/opt/fru/jobs/periodic.py"]
    environment = [
      { name = "SPARK_EXTRA_CONF", value = "spark.fru.delta_root=s3a://${var.delta_bucket}/delta" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.spark.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "spark"
      }
    }
  }])
  tags       = module.tags.common_tags
  depends_on = [aws_iam_role_policy_attachment.spark_exec_attach, aws_cloudwatch_log_group.spark]
}

resource "aws_iam_role" "events_invoke_ecs" {
  name = "${var.prefix}-${var.env}-events-invoke-ecs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = module.tags.common_tags
}

resource "aws_iam_role_policy" "events_invoke_ecs" {
  name = "${var.prefix}-${var.env}-events-invoke-ecs"
  role = aws_iam_role.events_invoke_ecs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ecs:RunTask"]
      Resource = [aws_ecs_task_definition.spark.arn]
      }, {
      Effect   = "Allow"
      Action   = ["iam:PassRole"]
      Resource = [aws_iam_role.spark_task_exec.arn]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "spark_schedule" {
  name                = "${var.prefix}-${var.env}-spark-schedule"
  schedule_expression = var.spark_schedule_expression
  tags                = module.tags.common_tags
}

data "aws_ecs_cluster" "main" {
  cluster_name = var.ecs_cluster_name
  depends_on   = [module.ecs_alb]
}

resource "aws_cloudwatch_event_target" "spark" {
  rule     = aws_cloudwatch_event_rule.spark_schedule.name
  arn      = data.aws_ecs_cluster.main.arn
  role_arn = aws_iam_role.events_invoke_ecs.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.spark.arn
    task_count          = 1
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = data.terraform_remote_state.shared_durable.outputs.private_subnet_ids
      security_groups  = [module.ecs_alb.tasks_security_group_id]
      assign_public_ip = false
    }
  }
}

module "frontend" {
  source = "../../infra-modules/aws/primitives/cloudfront"
  prefix = var.prefix
  env    = var.env
  suffix = "nonkube"

  alb_dns_name           = module.ecs_alb.alb_dns_name
  api_origin_id          = "ALB-${var.prefix}-${var.env}-nonkube"
  cloudfront_price_class = var.cloudfront_price_class
  certificate_arn        = var.certificate_arn
  tags                   = module.tags.common_tags
}

output "alb_dns_name" { value = module.ecs_alb.alb_dns_name }
output "ecs_service_name" { value = module.ecs_alb.service_name }
output "ecs_cluster_name" { value = module.ecs_alb.cluster_name }
output "ecs_task_definition_arn" { value = module.ecs_alb.task_definition_arn }
output "ecs_tasks_sg_id" { value = module.ecs_alb.tasks_security_group_id }
output "cloudfront_domain_name" { value = module.frontend.cloudfront_domain_name }
output "cloudfront_distribution_id" { value = module.frontend.cloudfront_distribution_id }
output "frontend_s3_bucket_id" { value = module.frontend.s3_bucket_id }
