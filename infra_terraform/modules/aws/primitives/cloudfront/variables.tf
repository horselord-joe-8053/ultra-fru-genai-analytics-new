variable "prefix" {
  type        = string
  description = "Project prefix (e.g. fru)"
}

variable "env" {
  type        = string
  description = "Environment (dev, prod)"
}

variable "suffix" {
  type        = string
  description = "Stack suffix (e.g. nonkube, kube) - distinguishes frontends"
}

variable "alb_dns_name" {
  type        = string
  description = "ALB or NLB DNS name for API origin - optional, for /query, /analytics paths"
  default     = null
}

variable "api_origin_id" {
  type        = string
  description = "Origin ID for API (ALB/NLB)"
  default     = null
}

variable "cloudfront_price_class" {
  type        = string
  description = "CloudFront price class"
  default     = "PriceClass_100"
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for CloudFront (must be in us-east-1)"
  default     = null
}

variable "enable_versioning" {
  type        = bool
  description = "Enable S3 bucket versioning"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Common tags"
  default     = {}
}
