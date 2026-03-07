# Durable-with-cooloff stack: Secrets Manager secrets only.
# Isolated from durable (VPC, Aurora) so that --incl-dura destroys VPC+Aurora
# but keeps secrets; --incl-dura-all destroys both. Avoids 30-day same-name
# block (cooloff period) when re-deploying after teardown. See docs/learned/cloud_shared/DURABLE_COOLOFF_MULTI_CLOUD.md.

terraform {
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

module "tags" {
  source = "../../../../modules/cloud_shared/primitives/tags"
  extra_tags = {
    environment = var.env
    scope       = "shared"
    durability  = "durable_with_cooloff"
  }
}

# Secrets containers (no secret values in Terraform state).
# Values set by tools/aws/ensure_secrets.py.
# recovery_window_in_days = 30: 30-day cool-off when deleted; use RestoreSecret to recover.
resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.prefix}/${var.env}/openai_api_key-${var.aws_region}"
  recovery_window_in_days = 30
  tags                    = module.tags.common_tags
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.prefix}/${var.env}/db_password-${var.aws_region}"
  recovery_window_in_days = 30
  tags                    = module.tags.common_tags
}

resource "aws_secretsmanager_secret" "db_password_plain" {
  name                    = "${var.prefix}/${var.env}/db_password_plain-${var.aws_region}"
  recovery_window_in_days = 30
  tags                    = module.tags.common_tags
}

output "openai_api_key_secret_arn"   { value = aws_secretsmanager_secret.openai_api_key.arn }
output "db_password_secret_arn"      { value = aws_secretsmanager_secret.db_password.arn }
output "db_password_plain_secret_arn" { value = aws_secretsmanager_secret.db_password_plain.arn }
output "db_secret_arn" { value = aws_secretsmanager_secret.db_password.arn }
