
variable "name" { type = string }
variable "aws_region" {
  type        = string
  description = "AWS region (used for global IAM role names to avoid cross-region teardown conflicts)"
}
variable "subnet_ids" { type = list(string) }
variable "instance_types" {
  type    = list(string)
  default = ["t3.small"]
}
variable "min_size" {
  type        = number
  description = "EKS node group minimum size"
}
variable "max_size" {
  type        = number
  description = "EKS node group maximum size"
}
variable "tags" {
  type    = map(string)
  default = {}
}
