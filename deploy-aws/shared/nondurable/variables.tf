
variable "env" { type = string }
variable "prefix" { type = string }
variable "aws_region" { type = string }

variable "delta_bucket" { type = string }
variable "artifacts_bucket" { type = string }
variable "ecr_repo_app" { type = string }
variable "ecr_repo_spark" { type = string }

variable "tf_state_bucket" { type = string }
variable "tf_lock_table" { type = string }
variable "tf_state_prefix" { type = string }
