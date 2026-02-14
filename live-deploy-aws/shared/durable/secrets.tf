
# Secrets containers (no secret values stored in Terraform state).
# Values should be set via tools/aws/ensure_secrets.py.

resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.prefix}/${var.env}/openai_api_key"
  recovery_window_in_days = 30
  tags                    = module.tags.common_tags
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.prefix}/${var.env}/db_password"
  recovery_window_in_days = 30
  tags                    = module.tags.common_tags
  lifecycle { prevent_destroy = true }
}

output "openai_api_key_secret_arn" { value = aws_secretsmanager_secret.openai_api_key.arn }
output "db_password_secret_arn" { value = aws_secretsmanager_secret.db_password.arn }
