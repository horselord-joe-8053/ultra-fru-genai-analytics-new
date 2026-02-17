
terraform { required_version = ">= 1.6.0" }

resource "aws_s3_bucket" "this" {
  bucket        = var.name
  force_destroy = var.force_destroy # Empty bucket before delete; avoids BucketNotEmpty on teardown
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "v" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration { status = var.versioning ? "Enabled" : "Suspended" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sse" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
