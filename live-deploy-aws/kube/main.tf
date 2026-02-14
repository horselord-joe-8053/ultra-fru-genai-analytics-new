
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

data "terraform_remote_state" "shared_nondurable" {
  backend = "s3"
  config = {
    bucket         = var.tf_state_bucket
    key            = "${var.tf_state_prefix}/${var.env}/aws-shared-nondurable.tfstate"
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

# Aurora ingress from EKS nodes (cluster SG) for DB connectivity
resource "aws_security_group_rule" "aurora_from_eks" {
  count                    = try(data.terraform_remote_state.shared_durable.outputs.aurora_security_group_id, "") != "" ? 1 : 0
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.eks.cluster_security_group_id
  security_group_id        = data.terraform_remote_state.shared_durable.outputs.aurora_security_group_id
  description              = "Aurora ingress from EKS cluster"
}

output "eks_cluster_name" { value = module.eks.cluster_name }
output "eks_endpoint" { value = module.eks.cluster_endpoint }
output "cloudfront_domain_name" { value = module.frontend.cloudfront_domain_name }
output "cloudfront_distribution_id" { value = module.frontend.cloudfront_distribution_id }
output "frontend_s3_bucket_id" { value = module.frontend.s3_bucket_id }
output "ecr_app_url" { value = data.terraform_remote_state.shared_nondurable.outputs.ecr_app_url }
output "ecr_spark_url" { value = data.terraform_remote_state.shared_nondurable.outputs.ecr_spark_url }
output "delta_bucket" { value = data.terraform_remote_state.shared_nondurable.outputs.delta_bucket }
