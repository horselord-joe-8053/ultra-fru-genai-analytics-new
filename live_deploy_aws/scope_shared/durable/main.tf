
terraform {
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

module "tags" {
  source = "../../../infra_modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "shared"
    durability  = "durable"
  }
}

module "vpc" {
  source               = "../../../infra_modules/aws/primitives/vpc"
  name                 = "${var.prefix}-${var.env}"
  cidr                 = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat           = true
  allow_destroy        = var.allow_destroy_durable
  tags                 = module.tags.common_tags
}

module "aurora" {
  source = "../../../infra_modules/aws/primitives/aurora"

  prefix              = var.prefix
  env                 = var.env
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  database_name       = var.aurora_database_name
  master_username     = var.aurora_master_username
  master_password     = var.aurora_master_password
  engine_version      = var.aurora_engine_version
  instance_class      = var.aurora_instance_class
  instance_count      = var.aurora_instance_count
  min_capacity        = var.aurora_min_capacity
  max_capacity        = var.aurora_max_capacity
  deletion_protection = var.aurora_deletion_protection
  tags                = module.tags.common_tags
}

output "vpc_id" { value = module.vpc.vpc_id }
output "public_subnet_ids" { value = module.vpc.public_subnet_ids }
output "private_subnet_ids" { value = module.vpc.private_subnet_ids }

output "aurora_endpoint"            { value = module.aurora.cluster_endpoint }
output "aurora_port"                { value = module.aurora.cluster_port }
output "aurora_database_name"       { value = module.aurora.database_name }
output "aurora_security_group_id"   { value = module.aurora.security_group_id }
output "aurora_cluster_arn"         { value = module.aurora.cluster_arn }
