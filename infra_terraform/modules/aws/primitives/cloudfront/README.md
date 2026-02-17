# CloudFront + S3 Frontend primitive

Reusable module: S3 bucket for static assets + CloudFront distribution with optional ALB/NLB origin for API paths.

## Inputs

- `prefix`, `env`, `suffix` — Used for naming (e.g. fru-dev-nonkube).
- `alb_dns_name` — Optional. ALB or NLB DNS name for API origin; when set, `/query`, `/analytics`, `/query/stream`, `/version` route to it.
- `api_origin_id` — Origin ID for the API origin.
- `cloudfront_price_class` — Default `PriceClass_100`.
- `certificate_arn` — Optional ACM cert (must be us-east-1) for custom domain.

## Usage

From `infra_terraform/live_deploy/aws/nonkube` or `infra_terraform/live_deploy/aws/kube`:

```hcl
module "frontend" {
  source = "../../infra_terraform/modules/aws/primitives/cloudfront"
  prefix = var.prefix
  env    = var.env
  suffix = "nonkube"  # or "kube"

  alb_dns_name = module.ecs.alb_dns_name  # or var.ingress_hostname for kube
  api_origin_id = "ALB-${var.prefix}-${var.env}-nonkube"
  tags = module.tags.common_tags
}
```

## Outputs

- `s3_bucket_id`, `s3_bucket_arn` — Frontend S3 bucket.
- `cloudfront_distribution_id`, `cloudfront_domain_name`, `cloudfront_arn` — CloudFront distribution.

## Deploying frontend assets

Terraform creates the bucket; you must deploy build artifacts separately (e.g. `aws s3 sync dist/ s3://<bucket>/`). Add CloudFront URLs to `ALLOWED_ORIGINS` for the API.
