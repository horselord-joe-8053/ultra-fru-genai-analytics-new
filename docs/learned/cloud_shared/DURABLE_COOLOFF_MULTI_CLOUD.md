# Durable-with-Cooloff: Multi-Cloud Reference

**Purpose:** Side-by-side comparison of `durable_with_cooloff` across cloud providers. Extensible for Oracle, Azure, Huawei, etc.

---

## 1. What Is durable_with_cooloff?

A Terraform stack holding **secrets only** (DB password, API keys), isolated from `durable` (VPC, DB):

- **Normal teardown** (`--incl-dura`): Destroys VPC + DB; <span style="color:#2e7d32">**secrets remain**</span>.
- **Full teardown** (`--incl-dura-all`): Destroys both durable and durable_with_cooloff.

---

## 2. Provider Comparison (Side-by-Side)

| Aspect | AWS | GCP | Oracle | Azure | Huawei |
|--------|-----|-----|-------|------|--------|
| **Secret service** | Secrets Manager | Secret Manager | Vault / OCI Vault | Key Vault | KMS / CSMS |
| **Same-name block after delete** | <span style="color:#c62828">Yes</span> (7–30 d) | <span style="color:#2e7d32">No</span> | TBD | TBD | TBD |
| **Recovery window** | 7–30 days | None | TBD | TBD | TBD |
| **Drives split?** | <span style="color:#2e7d32">Yes</span> | <span style="color:#757575">Parity only</span> | TBD | TBD | TBD |
| **Recovery API** | `RestoreSecret` | N/A | TBD | TBD | TBD |

---

## 3. Secret Resources in durable_with_cooloff (Side-by-Side)

| Secret | AWS | GCP | Oracle | Azure | Huawei |
|--------|-----|-----|--------|------|--------|
| openai_api_key | ✓ | ✓ | — | — | — |
| db_password | ✓ | ✓ | — | — | — |
| db_password_plain | ✓ | ✓ | — | — | — |
| google_ai_api_key | — | ✓ | — | — | — |
| claude_api_key | — | ✓ | — | — | — |

---

## 4. Cool-Off by Resource Type (Side-by-Side)

| Resource | AWS | GCP | Oracle | Azure | Huawei |
|----------|-----|-----|--------|------|--------|
| **Secrets (whole)** | <span style="color:#c62828">7–30 d</span> | <span style="color:#2e7d32">None</span> | TBD | TBD | TBD |
| **Secret versions** | — | Configurable | TBD | TBD | TBD |
| **KMS keys** | 7–30 d | 30 d default | TBD | TBD | TBD |
| **In our stacks?** | Secrets only | Secrets only | — | — | — |

---

## 5. Stack Paths & Purpose

| Provider | Stack path | Purpose |
|----------|------------|---------|
| AWS | `live_deploy/aws/scope_shared/durable_with_cooloff/` | Isolate secrets; avoid 30-day same-name block |
| GCP | `live_deploy/gcp/scope_shared/durable_with_cooloff/` | Structural parity (same phase order) |
| Oracle | `live_deploy/oracle/scope_shared/durable_with_cooloff/` | TBD |
| Azure | `live_deploy/azure/scope_shared/durable_with_cooloff/` | TBD |
| Huawei | `live_deploy/huawei/scope_shared/durable_with_cooloff/` | TBD |

---

## 6. Deploy & Teardown (Shared)

**Deploy order:** Doctor → Bootstrap → **durable_with_cooloff** → durable → nondurable → ensure_secrets → build → kube/nonkube

**Teardown order:** kube/nonkube → nondurable → durable → **durable_with_cooloff** (only with `--incl-dura-all`)

| Flag | Effect |
|------|--------|
| `--incl-dura` | Destroy durable (VPC, DB). Secrets remain. |
| `--incl-dura-all` | Destroy durable **and** durable_with_cooloff. Full teardown. |

---

## 7. Provider-Specific Recovery

### AWS

```bash
aws secretsmanager restore-secret --secret-id fru/dev/<name>-<region>
# Then: tofu import aws_secretsmanager_secret.<resource> <secret-id>
```

### GCP

No recovery needed—deletion is immediate; same-name recreate works.

### Oracle / Azure / Huawei

TBD when stacks are added.

---

## 8. Extending to New Providers

When adding Oracle, Azure, Huawei, or another provider:

1. **Research** the secret/key service: Does it have a deletion recovery window? Same-name block?
2. **Update Section 2** (Provider Comparison): Add column, fill Same-name block, Recovery window, Drives split.
3. **Update Section 3** (Secret Resources): Add column, list which secrets exist.
4. **Update Section 4** (Cool-Off by Resource): Add column for that provider’s secret/KMS behavior.
5. **Update Section 5** (Stack Paths): Add `live_deploy/<provider>/scope_shared/durable_with_cooloff/`.
6. **Update Section 7** (Recovery): Add recovery commands if the provider has a cool-off.
7. **Create stack** at `infra_terraform/live_deploy/<provider>/scope_shared/durable_with_cooloff/` (mirror AWS/GCP structure).

---

## 9. As Implemented

1. **`infra_terraform/live_deploy/aws/scope_shared/durable_with_cooloff/`** and **`live_deploy/gcp/scope_shared/durable_with_cooloff/`** exist with secrets only.
2. Secrets are standalone; durable has no secrets. Nondurable/kube read them via `tofu output` from durable. Deploy and tools read from both stacks as needed (durable_with_cooloff applied first).
3. **`teardown.py`:** `--incl-dura` destroys durable only (VPC, Aurora/Cloud SQL); secrets remain. `--incl-dura-all` destroys durable then durable_with_cooloff.
4. **Deploy:** Applies durable_with_cooloff before durable; tools read from the appropriate stack outputs.

### Why `recovery_window_in_days = 30` (AWS)

The `recovery_window_in_days` parameter controls the AWS Secrets Manager recovery window. When Terraform destroys a secret, AWS schedules it for deletion. During that period (default 30 days): the secret is in "scheduled for deletion" state; **you cannot create a new secret with the same name** until the old one is either restored or permanently deleted. We set it explicitly for recovery capability (restore if teardown was accidental); the cool-off is the unavoidable consequence. **Alternative:** `ForceDeleteWithoutRecovery` would allow immediate same-name recreation but is irreversible—we do not use it.

### Migration (Existing Deployments)

If you have an **existing** deployment where secrets are in the `durable` state:

1. **Import** existing secrets into durable_with_cooloff (deploy does this automatically).
2. **Remove secrets from durable state** (keeps secrets in AWS):
   ```bash
   cd infra_terraform/live_deploy/aws/scope_shared/durable
   tofu state rm aws_secretsmanager_secret.openai_api_key
   tofu state rm aws_secretsmanager_secret.db_password
   tofu state rm aws_secretsmanager_secret.db_password_plain
   ```
3. **Apply durable** — it will read secret ARNs from durable_with_cooloff via remote state.

For **fresh** deployments, no migration needed.

---

## 10. Related Docs

- [GCP_AWS_REFERENCE.md](../../GCP_AWS_REFERENCE.md) — Component mapping
- [WAR_STORIES_CLOUD_SHARED.md](../../war_stories/WAR_STORIES_CLOUD_SHARED.md) — War story #36 (phase order)
