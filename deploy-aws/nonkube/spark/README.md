
# Spark on ECS (Scheduled)

This project provides the ECS task definition JSON and helper scripts in `tools/` to:
- register task definition
- run bootstrap task once
- create EventBridge schedule

We keep this orchestration thin and explicit; Terraform can manage it later.
