variable "prefix" {
  type        = string
  description = "Project prefix (e.g., fru)"
}

variable "env" {
  type        = string
  description = "Environment (dev, prod)"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for Aurora"
}

variable "database_name" {
  type        = string
  description = "Default database name"
  default     = "fru_db"
}

variable "master_username" {
  type        = string
  description = "Master username"
  default     = "postgres"
}

variable "master_password" {
  type        = string
  description = "Master password (from Secrets Manager or .env)"
  sensitive   = true
}

variable "engine_version" {
  type        = string
  description = "Aurora PostgreSQL engine version"
  default     = "16.4"
}

variable "instance_class" {
  type        = string
  description = "Instance class for Serverless v2"
  default     = "db.serverless"
}

variable "instance_count" {
  type        = number
  description = "Number of instances"
  default     = 1
}

variable "min_capacity" {
  type        = number
  description = "Min ACU for Serverless v2"
  default     = 0.5
}

variable "max_capacity" {
  type        = number
  description = "Max ACU for Serverless v2"
  default     = 16
}

variable "enable_iam_auth" {
  type        = bool
  description = "Enable IAM database authentication"
  default     = false
}

variable "backup_retention_period" {
  type        = number
  default     = 7
}

variable "preferred_backup_window" {
  type        = string
  default     = "03:00-04:00"
}

variable "kms_key_id" {
  type        = string
  default     = null
}

variable "deletion_protection" {
  type        = bool
  default     = false
}

variable "tags" {
  type        = map(string)
  default     = {}
}
