# Deployment Run Optimization: Refactor Plans

Concise refactor plans for the identified deployment optimizations. All implemented.

### Estimated Time Savings for Re-Deploy (when state is clean)

| Optimization | Typical savings | When it applies |
|--------------|-----------------|-----------------|
| **2.1** VPC tag lifecycle | ~30–60 s | Avoids durable apply touching subnets (tag drift); kube no longer re-adds tags. |
| **2.2** Single kube apply | ~1–5 min | Re-deploy: hostname known before first apply → skip second apply. |
| **2.3** Skip import + apply | ~2–8 min per stack | Plan shows no changes → skip import and Terraform apply for that stack. |
| **2.4** Content-based build skip | ~3–10 min | Hash matches → skip Docker build and push. |

**Rough total for a clean full-scope re-deploy:** ~5–20 minutes saved.

---

## 2.1 Durable vs Kube Subnet Tags

**Why Kube adds tags:** `kubernetes.io/role/elb` and `kubernetes.io/cluster/<cluster_name>` enable LB placement in public subnets. Without them → NLB in private subnets → CloudFront 502. See War Story 43 and [KUBE_INGRESS_LEARNED.md](KUBE_INGRESS_LEARNED.md) Section 0.

**Drift cycle:** Durable creates subnets (no k8s tags). Kube adds tags via `aws_ec2_tag`. Durable's next apply sees "extra" tags and plans to remove them. Kube re-adds. Repeat.

**Fix:** `lifecycle { ignore_changes = [tags] }` on subnet resources in `infra_terraform/modules/aws/primitives/vpc/main.tf`. See [docs/war_stories/WAR_STORIES_AWS.md](../war_stories/WAR_STORIES_AWS.md) War Story 58.

---

## 2.2 Single Kube Apply When Hostname Known

**Why twice:** LB hostname unknown until k8s creates Service. First apply (no hostname) → kube_apply → poll → second apply (with hostname for CloudFront).

**Fix:** `_try_get_lb_hostname` before first apply; skip second apply when hostname already known. See [docs/war_stories](../war_stories/). War Story 59.

---

## 2.3 Skip Import + Apply When Plan Clean

**Fix:** `plan_shows_no_changes()` before import; skip import and apply when plan shows no changes. See [docs/war_stories](../war_stories/). War Story 60.

---

## 2.4 Content-Based Build Skip

**Fix:** Build-context hash (S3/AWS, GCS/GCP); skip build when hash matches. `--force-build` bypasses. See [BUILD_CONTENT_SKIP.md](BUILD_CONTENT_SKIP.md). War Story 61.
