# GCP Cloud Storage Bucket Module
# Equivalent to AWS S3 bucket

variable "name" {
  description = "Name of the GCS bucket"
  type        = string
}

variable "location" {
  description = "GCP region or multi-region for the bucket"
  type        = string
  default     = "US"
}

variable "force_destroy" {
  description = "Allow non-empty bucket deletion"
  type        = bool
  default     = false
}

variable "versioning_enabled" {
  description = "Enable object versioning"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Labels to apply to the bucket"
  type        = map(string)
  default     = {}
}
