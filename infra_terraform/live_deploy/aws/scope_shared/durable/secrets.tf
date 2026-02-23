
# Secrets containers (no secret values stored in Terraform state).
# Values should be set via tools/aws/ensure_secrets.py.
#
# Legacy pattern (module_infra_longterm): two secrets for DB password:
# - db_password (JSON): for RDS Data API (setup_database, load_data)
# - db_password_plain (plain string): for ECS task definitions (ECS doesn't support JSON key extraction)

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

# Plain string for ECS (legacy: aurora-db-password-plain)
resource "aws_secretsmanager_secret" "db_password_plain" {
  name                    = "${var.prefix}/${var.env}/db_password_plain-${var.aws_region}"
  recovery_window_in_days = 30
  tags                    = module.tags.common_tags
}

output "openai_api_key_secret_arn"   { value = aws_secretsmanager_secret.openai_api_key.arn }
output "db_password_secret_arn"      { value = aws_secretsmanager_secret.db_password.arn }
output "db_password_plain_secret_arn" { value = aws_secretsmanager_secret.db_password_plain.arn }
# For RDS Data API (setup_database, ETL): use db_password_secret_arn
output "db_secret_arn" { value = aws_secretsmanager_secret.db_password.arn }
