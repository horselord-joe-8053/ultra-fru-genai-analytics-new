# GCP VPC Module - Placeholder
# Equivalent to AWS VPC with subnets

variable "name" {
  description = "Name of the VPC network"
  type        = string
}

variable "cidr" {
  description = "Primary CIDR range for the network"
  type        = string
}

variable "enabled_nat" {
  description = "Enable NAT gateway for private subnets"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Labels to apply to network resources"
  type        = map(string)
  default     = {}
}
