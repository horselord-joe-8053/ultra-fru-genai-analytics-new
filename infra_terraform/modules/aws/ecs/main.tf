# ECS cluster + ALB + API service + Spark schedule (EventBridge -> ECS RunTask)
# Combined module for consistency with infra_terraform/modules/aws/eks

# ---- ECS ALB (cluster, ALB, API service) ----
resource "aws_cloudwatch_log_group" "ecs" {
  name              = var.cloudwatch_log_group_ecs_api != "" ? var.cloudwatch_log_group_ecs_api : "/${var.name}/${var.env}/ecs-api"
  retention_in_days  = 14
  tags              = var.tags
}

resource "aws_ecs_cluster" "main" {
  name = var.cluster_name
  tags = merge(var.tags, { Name = var.cluster_name })
}

resource "aws_security_group" "alb" {
  name        = "${var.alb_name}-sg"
  description = "ALB SG"
  vpc_id      = var.vpc_id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${var.alb_name}-sg" })
}

resource "aws_lb" "main" {
  name               = var.alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
  tags               = merge(var.tags, { Name = var.alb_name })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.alb_name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path = "/health"
  }

  tags = var.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_security_group" "tasks" {
  name        = "${var.name}-ecs-tasks-sg"
  description = "ECS tasks SG"
  vpc_id      = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${var.name}-ecs-tasks-sg" })
}

resource "aws_security_group_rule" "tasks_from_alb" {
  type                     = "ingress"
  from_port                = var.container_port
  to_port                  = var.container_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.tasks.id
  description              = "Allow inbound from ALB"
}

resource "aws_security_group_rule" "aurora_from_ecs" {
  count                    = var.aurora_security_group_id != "" ? 1 : 0
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.tasks.id
  security_group_id        = var.aurora_security_group_id
  description              = "Allow ECS tasks to reach Aurora"
}

locals {
  role_suffix = var.aws_region
}

resource "aws_iam_role" "exec" {
  name = "${var.name}-${var.env}-ecs-exec-${local.role_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}
resource "aws_iam_role_policy_attachment" "exec_attach" {
  role       = aws_iam_role.exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "exec_secrets" {
  count       = length(var.secret_arns) > 0 ? 1 : 0
  name        = "${var.name}-${var.env}-ecs-exec-secrets-${local.role_suffix}"
  role        = aws_iam_role.exec.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [for arn in values(var.secret_arns) : arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-${var.env}-ecs-task-${local.role_suffix}"
  assume_role_policy = aws_iam_role.exec.assume_role_policy
  tags               = var.tags
}

resource "aws_iam_role_policy" "task_bedrock" {
  name = "${var.name}-${var.env}-ecs-task-bedrock-${local.role_suffix}"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
      Resource = ["*"]
    }]
  })
}

locals {
  env_list     = [for k, v in var.env_vars : { name = k, value = v }]
  secrets_list = [for k, v in var.secret_arns : { name = k, valueFrom = v }]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-${var.env}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = var.container_name
    image     = var.app_image
    essential = true
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    environment = local.env_list
    secrets     = local.secrets_list
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "ecs"
      }
    }
  }])

  depends_on = [aws_iam_role_policy_attachment.exec_attach, aws_cloudwatch_log_group.ecs]
  tags       = var.tags
}

data "aws_region" "current" {}

resource "aws_ecs_service" "api" {
  name            = "${var.name}-${var.env}-api-svc"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = var.container_name
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]
  tags       = var.tags
}

# ---- Spark schedule (EventBridge -> ECS RunTask) ----
resource "aws_cloudwatch_log_group" "spark" {
  name              = var.cloudwatch_log_group_spark != "" ? var.cloudwatch_log_group_spark : "/${var.name}/${var.env}/spark"
  retention_in_days  = 14
  tags              = var.tags
}

resource "aws_iam_role" "spark_task_exec" {
  name = "${var.name}-${var.env}-spark-task-exec-${local.role_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "spark_exec_attach" {
  role       = aws_iam_role.spark_task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "spark_s3" {
  name = "${var.name}-${var.env}-spark-s3-${local.role_suffix}"
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

# Task role: used by container for AWS SDK (S3, etc). Execution role is for ECS agent only.
resource "aws_iam_role" "spark_task" {
  name = "${var.name}-${var.env}-spark-task-${local.role_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "spark_task_s3" {
  name = "${var.name}-${var.env}-spark-task-s3-${local.role_suffix}"
  role = aws_iam_role.spark_task.id
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

resource "aws_iam_role_policy" "spark_secrets" {
  count       = var.db_password_plain_secret_arn != "" ? 1 : 0
  name        = "${var.name}-${var.env}-spark-secrets-${local.role_suffix}"
  role        = aws_iam_role.spark_task_exec.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.db_password_plain_secret_arn]
    }]
  })
}

locals {
  spark_env = concat(
    [
      { name = "CLOUD_PROVIDER", value = "aws" },
      { name = "SPARK_EXTRA_CONF", value = "spark.fru.delta_root=s3a://${var.delta_bucket}/delta" },
      { name = "DELTA_TABLE_PATH", value = "s3a://${var.delta_bucket}/delta/fru_sales" }
    ],
    var.aurora_endpoint != "" ? [
      { name = "PGHOST", value = var.aurora_endpoint },
      { name = "PGPORT", value = var.aurora_port },
      { name = "PGDATABASE", value = var.aurora_database_name },
      { name = "PGUSER", value = "postgres" }
    ] : []
  )
  spark_secrets = var.db_password_plain_secret_arn != "" ? [
    { name = "PGPASSWORD", valueFrom = var.db_password_plain_secret_arn }
  ] : []
}

resource "aws_ecs_task_definition" "spark" {
  family                   = "${var.name}-${var.env}-spark"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.spark_task_exec.arn
  task_role_arn            = aws_iam_role.spark_task.arn
  container_definitions = jsonencode([{
    name        = "spark"
    image       = var.spark_image
    essential   = true
    command     = ["/opt/spark/bin/spark-submit", "--packages", "io.delta:delta-spark_2.13:4.0.0,io.delta:delta-storage:4.0.0,org.apache.hadoop:hadoop-aws:3.3.4", "/opt/fru/jobs/run_analytics.py"]
    environment = local.spark_env
    secrets     = local.spark_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.spark.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "spark"
      }
    }
  }])
  tags       = var.tags
  depends_on = [aws_iam_role_policy_attachment.spark_exec_attach, aws_cloudwatch_log_group.spark]
}

resource "aws_iam_role" "events_invoke_ecs" {
  name = "${var.name}-${var.env}-events-invoke-ecs-${local.role_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "events_invoke_ecs" {
  name = "${var.name}-${var.env}-events-invoke-ecs-${local.role_suffix}"
  role = aws_iam_role.events_invoke_ecs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.spark.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [aws_iam_role.spark_task_exec.arn, aws_iam_role.spark_task.arn]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "spark_schedule" {
  name                = "${var.name}-${var.env}-spark-schedule"
  schedule_expression = var.spark_schedule_expression
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "spark" {
  rule     = aws_cloudwatch_event_rule.spark_schedule.name
  arn      = aws_ecs_cluster.main.arn
  role_arn = aws_iam_role.events_invoke_ecs.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.spark.arn
    task_count          = 1
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = var.private_subnet_ids
      security_groups  = [aws_security_group.tasks.id]
      assign_public_ip = false
    }
  }
}
