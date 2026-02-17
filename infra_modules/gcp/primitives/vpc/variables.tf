# GCP VPC Module
# Equivalent to AWS VPC with subnets

variable "name" {
  description = "Name of the VPC network"
  type        = string
}

variable "auto_create_subnetworks" {
  description = "When true, GCP creates subnets automatically per region"
  type        = bool
  default     = true
}

variable "cidr" {
  description = "Primary CIDR range (used when auto_create_subnetworks = false)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Labels to apply to network resources"
  type        = map(string)
  default     = {}
}
