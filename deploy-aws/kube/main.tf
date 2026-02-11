
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
    bucket         = var.tf_state_bucket
    key            = "${var.tf_state_prefix}/${var.env}/aws-shared-durable.tfstate"
    region         = var.aws_region
    dynamodb_table = var.tf_lock_table
    encrypt        = true
    use_lockfile   = true
  }
}

module "tags" {
  source = "../../infra-modules/shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "kube"
    durability  = "nondurable"
  }
}

module "eks" {
  source         = "../../infra-modules/aws/eks"
  name           = var.eks_cluster_name
  subnet_ids     = data.terraform_remote_state.shared_durable.outputs.private_subnet_ids
  instance_types = var.eks_instance_types
  desired_size   = var.eks_desired_nodes
  tags           = module.tags.common_tags
}

# CloudFront + S3 frontend (alb_dns_name = null until Ingress/NLB is added)
module "frontend" {
  source = "../../infra-modules/aws/primitives/cloudfront"
  prefix = var.prefix
  env    = var.env
  suffix = "kube"

  alb_dns_name           = var.ingress_hostname
  api_origin_id          = "ALB-${var.prefix}-${var.env}-kube"
  cloudfront_price_class = var.cloudfront_price_class
  certificate_arn        = var.certificate_arn
  tags                   = module.tags.common_tags
}

output "eks_cluster_name" { value = module.eks.cluster_name }
output "eks_endpoint" { value = module.eks.cluster_endpoint }
output "cloudfront_domain_name" { value = module.frontend.cloudfront_domain_name }
output "cloudfront_distribution_id" { value = module.frontend.cloudfront_distribution_id }
output "frontend_s3_bucket_id" { value = module.frontend.s3_bucket_id }
