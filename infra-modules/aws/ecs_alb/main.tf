
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/fru/${var.env}/ecs-api"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_ecs_cluster" "main" {
  name = var.cluster_name
  tags = merge(var.tags, { Name = var.cluster_name })
}

# ALB SG
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

# ECS tasks SG: allow inbound only from ALB
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

# Execution role (ECR pull + logs)
resource "aws_iam_role" "exec" {
  name = "${var.name}-${var.env}-ecs-exec"
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

# Runtime role (extend later for Bedrock/RDS/etc)
resource "aws_iam_role" "task" {
  name               = "${var.name}-${var.env}-ecs-task"
  assume_role_policy = aws_iam_role.exec.assume_role_policy
  tags               = var.tags
}

# Task definition
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
