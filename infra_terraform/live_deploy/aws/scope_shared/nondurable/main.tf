
terraform {
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

module "tags" {
  source = "../../../../modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "shared"
    durability  = "nondurable"
  }
}

module "delta_bucket" {
  source = "../../../../modules/aws/primitives/s3_bucket"
  name   = var.delta_bucket
  tags   = module.tags.common_tags
}

module "artifacts_bucket" {
  source = "../../../../modules/aws/primitives/s3_bucket"
  name   = var.artifacts_bucket
  tags   = module.tags.common_tags
}

module "ecr_app" {
  source = "../../../../modules/aws/primitives/ecr"
  name   = var.ecr_repo_app
  tags   = module.tags.common_tags
}

module "ecr_spark" {
  source = "../../../../modules/aws/primitives/ecr"
  name   = var.ecr_repo_spark
  tags   = module.tags.common_tags
}

output "delta_bucket" { value = module.delta_bucket.bucket_name }
output "artifacts_bucket" { value = module.artifacts_bucket.bucket_name }
output "ecr_app_url" { value = module.ecr_app.repository_url }
output "ecr_spark_url" { value = module.ecr_spark.repository_url }
