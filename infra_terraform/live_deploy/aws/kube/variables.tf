
variable "env" { type = string }
variable "prefix" { type = string }
variable "aws_region" { type = string }

variable "eks_cluster_name" { type = string }
variable "eks_instance_types" {
  type    = list(string)
  default = ["t3.small"]
}
variable "eks_desired_nodes" {
  type    = number
  default = 1
}

variable "tf_state_bucket" { type = string }
variable "tf_state_bucket_region" { type = string }
variable "tf_lock_table" { type = string }
variable "tf_state_prefix" { type = string }

# LB hostname for CloudFront API origin. Set after fru-api-svc LoadBalancer is provisioned (currently Classic ELB; NLB with aws-load-balancer-type annotation).
variable "ingress_hostname" {
  type    = string
  default = null
}
variable "cloudfront_price_class" {
  type    = string
  default = "PriceClass_100"
}
variable "certificate_arn" {
  type    = string
  default = null
}
