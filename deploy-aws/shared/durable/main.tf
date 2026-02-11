
terraform {
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

module "tags" {
  source = "../../../infra-modules/shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "shared"
    durability  = "durable"
  }
}

module "vpc" {
  source               = "../../../infra-modules/aws/primitives/vpc"
  name                 = "${var.prefix}-${var.env}"
  cidr                 = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat           = true
  allow_destroy        = var.allow_destroy_durable
  tags                 = module.tags.common_tags
}

output "vpc_id" { value = module.vpc.vpc_id }
output "public_subnet_ids" { value = module.vpc.public_subnet_ids }
output "private_subnet_ids" { value = module.vpc.private_subnet_ids }
