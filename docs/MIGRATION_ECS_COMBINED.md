# Migration: ecs_alb + ecs_spark_schedule → ecs

After combining `ecs_alb` and `ecs_spark_schedule` into `infra_terraform/modules/aws/ecs`, existing nonkube state must be migrated to avoid destroy/recreate.

## Prerequisites

- Run from repo root with `.env` loaded
- `tofu` (or `terraform`) in PATH
- Backend configured for `infra_terraform/live_deploy/aws/nonkube`

## Option A: State migration (preserves resources)

From repo root, with `TF_DATA_DIR` set and backend init done:

```bash
cd infra_terraform/live_deploy/aws/nonkube
export TF_DATA_DIR="$(pwd)/../tofu_data"

# Move ecs_alb resources into module.ecs
tofu state mv 'module.ecs_alb' 'module.ecs'

# Move ecs_spark_schedule resources into module.ecs (merge)
# Note: This will fail if ecs_alb resources already exist under module.ecs.
# Run the first mv, then mv each ecs_spark_schedule resource:
tofu state mv 'module.ecs_spark_schedule.aws_cloudwatch_log_group.spark' 'module.ecs.aws_cloudwatch_log_group.spark'
tofu state mv 'module.ecs_spark_schedule.aws_iam_role.spark_task_exec' 'module.ecs.aws_iam_role.spark_task_exec'
tofu state mv 'module.ecs_spark_schedule.aws_iam_role_policy_attachment.spark_exec_attach' 'module.ecs.aws_iam_role_policy_attachment.spark_exec_attach'
tofu state mv 'module.ecs_spark_schedule.aws_iam_role_policy.spark_s3' 'module.ecs.aws_iam_role_policy.spark_s3'
tofu state mv 'module.ecs_spark_schedule.aws_ecs_task_definition.spark' 'module.ecs.aws_ecs_task_definition.spark'
tofu state mv 'module.ecs_spark_schedule.aws_iam_role.events_invoke_ecs' 'module.ecs.aws_iam_role.events_invoke_ecs'
tofu state mv 'module.ecs_spark_schedule.aws_iam_role_policy.events_invoke_ecs' 'module.ecs.aws_iam_role_policy.events_invoke_ecs'
tofu state mv 'module.ecs_spark_schedule.aws_cloudwatch_event_rule.spark_schedule' 'module.ecs.aws_cloudwatch_event_rule.spark_schedule'
tofu state mv 'module.ecs_spark_schedule.aws_cloudwatch_event_target.spark' 'module.ecs.aws_cloudwatch_event_target.spark'
```

**Order:** Run the `module.ecs_alb` → `module.ecs` mv first, then mv each `ecs_spark_schedule` resource into `module.ecs`.

## Option B: Destroy + redeploy (downtime)

If migration is not critical:

```bash
python tools/aws/teardown.py --scope nonkube --env dev --force
python tools/aws/deploy.py --scope nonkube --env dev
```

This destroys and recreates all nonkube resources.

---

## See Also

- **[FINAL_REFACTOR_PLAN.md](./FINAL_REFACTOR_PLAN.md)** – Consolidated refactor plan (Aurora, DB setup, PG* env vars)
