# Next Steps: IAM Role Region Suffix Migration

## What Changed

All **global** IAM roles now include a region suffix to avoid cross-region teardown deleting roles used by another region:

| Stack   | Old Name              | New Name                          |
|---------|------------------------|-----------------------------------|
| nonkube | fru-dev-ecs-exec       | fru-dev-ecs-exec-us-east-1        |
| nonkube | fru-dev-ecs-task       | fru-dev-ecs-task-us-east-1        |
| nonkube | fru-dev-spark-task-exec| fru-dev-spark-task-exec-us-east-1 |
| nonkube | fru-dev-spark-task     | fru-dev-spark-task-us-east-1      |
| nonkube | fru-dev-events-invoke-ecs | fru-dev-events-invoke-ecs-us-east-1 |
| kube    | fru-dev-eks-cluster-role | fru-dev-eks-cluster-role-us-east-1 |
| kube    | fru-dev-eks-node-role  | fru-dev-eks-node-role-us-east-1   |

---

## What To Do Next

### 1. Deploy nonkube for us-east-1 (fixes Bedrock)

The `fru-dev-ecs-task` role was deleted (likely by us-east-2 teardown). Deploy will create the new region-suffixed role and wire ECS to it.

```bash
cd /path/to/fru-genai-analytics-new
CLOUD_REGION=us-east-1 python orchestrator.py deploy --scope nonkube --env dev --cloud-region us-east-1
```

**If apply fails** with "role not found" or "NoSuchEntity" during destroy of the old roles, remove the stale role resources from state first:

```bash
cd infra_terraform/live_deploy/aws/nonkube
# Init with us-east-1 backend
CLOUD_REGION=us-east-1 tofu init -reconfigure  # (use your normal backend config)

# Remove stale roles from state (they were already deleted by teardown)
tofu state rm 'module.ecs.aws_iam_role.exec' 2>/dev/null || true
tofu state rm 'module.ecs.aws_iam_role.task' 2>/dev/null || true
tofu state rm 'module.ecs.aws_iam_role.spark_task_exec' 2>/dev/null || true
tofu state rm 'module.ecs.aws_iam_role.spark_task' 2>/dev/null || true
tofu state rm 'module.ecs.aws_iam_role.events_invoke_ecs' 2>/dev/null || true

# Then apply
CLOUD_REGION=us-east-1 tofu apply -auto-approve
```

Or use the full deploy again after the state rm.

---

### 2. Deploy kube for us-east-1 (if needed)

If you use kube in us-east-1 and want region-suffixed EKS roles:

```bash
CLOUD_REGION=us-east-1 python orchestrator.py deploy --scope kube --env dev --cloud-region us-east-1
```

**If apply fails** with "role not found" during destroy of old EKS roles:

```bash
cd infra_terraform/live_deploy/aws/kube
tofu state rm 'module.eks.aws_iam_role.eks_cluster' 2>/dev/null || true
tofu state rm 'module.eks.aws_iam_role.eks_nodes' 2>/dev/null || true
# Then deploy again
```

---

### 3. Stale Components (Nothing to Remove)

- **Old roles** (`fru-dev-ecs-task`, etc.): Already deleted; no manual cleanup.
- **us-east-2**: Only shared-durable remains (no nonkube/kube). No stale IAM roles there.

---

### 4. Verify

After nonkube and kube deploy:

```bash
CLOUD_REGION=us-east-1 python orchestrator.py verify --scope all --env dev --cloud-region us-east-1
```

---

### 5. Migration Complete (2026-02-24)

- nonkube us-east-1: deployed with region-suffixed IAM roles
- kube us-east-1: deployed with region-suffixed EKS roles; full verify passed

---

### 6. Future Teardowns

With region-suffixed roles, tearing down us-east-2 will only destroy `fru-dev-*-us-east-2` roles. us-east-1 roles (`fru-dev-*-us-east-1`) stay intact.
