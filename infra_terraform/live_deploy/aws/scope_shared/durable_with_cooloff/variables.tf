# Variables for durable_with_cooloff stack (Secrets Manager only).
# 30-day recovery window: when destroyed, secrets stay in "scheduled for deletion"
# for 30 days; same-name recreation blocked until then. See docs/learned/DURABLE_COOLOFF_EVALUATION.md.

variable "prefix" { type = string }
variable "env" { type = string }
variable "aws_region" { type = string }

variable "tf_state_bucket" { type = string }
variable "tf_state_bucket_region" { type = string }
variable "tf_lock_table" { type = string }
variable "tf_state_prefix" { type = string }
