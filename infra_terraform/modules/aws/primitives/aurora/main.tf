# Aurora PostgreSQL (pgvector) - Serverless v2
# pgvector extension installed via SQL after creation (setup_database.py)

resource "aws_db_subnet_group" "aurora" {
  name       = "${var.prefix}-${var.env}-aurora-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.tags,
    { Name = "${var.prefix}-${var.env}-aurora-subnet-group" }
  )
}

resource "aws_security_group" "aurora" {
  name        = "${var.prefix}-${var.env}-aurora-sg"
  description = "Security group for Aurora PostgreSQL cluster"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.prefix}-${var.env}-aurora-sg" })
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier     = "${var.prefix}-${var.env}-aurora-cluster"
  engine                 = "aurora-postgresql"
  engine_version         = var.engine_version
  database_name          = var.database_name
  master_username        = var.master_username
  master_password        = var.master_password
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  enable_http_endpoint               = true
  iam_database_authentication_enabled = var.enable_iam_auth

  backup_retention_period = var.backup_retention_period
  preferred_backup_window = var.preferred_backup_window

  storage_encrypted = true
  kms_key_id       = var.kms_key_id

  deletion_protection = var.deletion_protection
  skip_final_snapshot = !var.deletion_protection

  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = merge(var.tags, { Name = "${var.prefix}-${var.env}-aurora-cluster" })
}

resource "aws_rds_cluster_instance" "aurora" {
  count              = var.instance_count
  identifier         = "${var.prefix}-${var.env}-aurora-instance-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  publicly_accessible = false

  tags = merge(var.tags, { Name = "${var.prefix}-${var.env}-aurora-instance-${count.index + 1}" })
}
