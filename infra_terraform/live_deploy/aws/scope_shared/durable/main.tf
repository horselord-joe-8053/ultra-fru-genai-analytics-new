# Durable stack: VPC, Aurora (no Secrets Manager—those live in durable_with_cooloff).
# Secret ARNs re-exported from durable_with_cooloff so kube/nonkube read from this stack.
# Apply order: durable_with_cooloff first, then durable.

terraform {
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

data "terraform_remote_state" "durable_with_cooloff" {
  backend = "s3"
  config = {
    bucket         = var.tf_state_bucket
    key            = "${var.tf_state_prefix}/${var.env}/${var.aws_region}/aws-shared-durable_with_cooloff.tfstate"
    region         = var.tf_state_bucket_region
    dynamodb_table = var.tf_lock_table
    encrypt        = true
    use_lockfile   = true
  }
}

module "tags" {
  source = "../../../../modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "shared"
    durability  = "durable"
  }
}

module "vpc" {
  source               = "../../../../modules/aws/primitives/vpc"
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
  source = "../../../../modules/aws/primitives/aurora"

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

# Re-export secret ARNs from durable_with_cooloff so kube/nonkube read from this stack.
output "openai_api_key_secret_arn"   { value = data.terraform_remote_state.durable_with_cooloff.outputs.openai_api_key_secret_arn }
output "db_password_secret_arn"      { value = data.terraform_remote_state.durable_with_cooloff.outputs.db_password_secret_arn }
output "db_password_plain_secret_arn" { value = data.terraform_remote_state.durable_with_cooloff.outputs.db_password_plain_secret_arn }
output "db_secret_arn" { value = data.terraform_remote_state.durable_with_cooloff.outputs.db_secret_arn }
