# GCP Cloud Storage Bucket Module - Placeholder
# Equivalent to AWS S3 bucket

variable "name" {
  description = "Name of the GCS bucket"
  type        = string
}

variable "tags" {
  description = "Labels to apply to the bucket"
  type        = map(string)
  default     = {}
}
