# EKS Node "Kubelet Stopped Posting Node Status" and CronJob Overload

**Keywords:** EKS, kubelet, NotReady, unreachable, t3.small, CronJob, concurrencyPolicy, Spark, fru-api Pending

---

## 1. Symptoms

- EKS nodes transition to **NotReady** with `node.kubernetes.io/unreachable` taint
- Node conditions show: `NodeStatusUnknown` — "Kubelet stopped posting node status"
- **fru-api** pods stay **Pending** — scheduler reports "Too many pods" or "no nodes available"
- Replacement nodes exhibit the same behavior within ~3 minutes of boot
- EC2 instances appear healthy; the issue is at the kubelet/application layer

---

## 2. Root Cause (Observed)

| Factor | Effect |
|--------|--------|
| **t3.small** (2 vCPU, 2GB RAM) | Minimal headroom for system + workload |
| **CronJob `concurrencyPolicy: Allow`** (default) | New Job every 5 min; 60+ Jobs accumulate over days |
| **No `ttlSecondsAfterFinished`** | Completed/failed Jobs and their pods persist |
| **Spark analytics pods** | JVM + driver + local executors; no resource limits; ~512MB–1GB+ per pod |
| **maxPods=11** (t3.small) | 5+ Spark pods + 2 fru-api + daemonsets → node at capacity |
| **Memory pressure** | Multiple Spark pods on 2GB node → OOM or kubelet starvation → kubelet stops |

When the node is overloaded, kubelet can stop responding. Replacement nodes boot, get scheduled the same workload, and fail again.

---

## 3. Fixes Applied

### 3.1. Immediate (Cluster Recovery)

1. **Suspend CronJob** to stop new Jobs:
   ```bash
   kubectl patch cronjob fru-analytics-periodic-kube -n fru-kube -p '{"spec":{"suspend":true}}'
   ```

2. **Delete periodic Jobs** to free pod slots (preserve bootstrap if desired):
   ```bash
   kubectl get jobs -n fru-kube -o name | grep periodic | xargs kubectl delete -n fru-kube
   ```
   Or delete all: `kubectl delete jobs -n fru-kube --all` (deploy will re-run bootstrap).

3. **Force-delete stuck Terminating pods** on unreachable nodes:
   ```bash
   kubectl delete pod <pod> -n fru-kube --force --grace-period=0
   ```

4. **Terminate NotReady EC2 instance** to trigger ASG replacement (optional if node never recovers):
   ```bash
   # Get instance ID from providerID (e.g. aws:///us-east-1b/i-0abc123 → i-0abc123)
   kubectl get node -o jsonpath='{.items[0].spec.providerID}' | sed 's|.*/||'
   AWS_PROFILE=admin aws ec2 terminate-instances --instance-ids <id> --region <region>
   ```

5. **Re-enable CronJob** after cluster recovers and fru-api pods are Running:
   ```bash
   kubectl patch cronjob fru-analytics-periodic-kube -n fru-kube -p '{"spec":{"suspend":false}}'
   ```

### 3.2. Prevent Recurrence (Manifest Changes)

1. **CronJob: `concurrencyPolicy: Forbid`** — only one Job at a time
2. **CronJob Job template: `ttlSecondsAfterFinished: 240`** — auto-cleanup after 4 min
3. **Consider** `desired_size=2` or `t3.medium` for node group if workload is heavy

---

## 4. Diagnosing Root Cause: Why Did the Node Become Unreachable?

**Do not blindly replace the node.** Something caused a working node to transition to NotReady. Replacing it fixes the symptom but not the cause; the next deploy may trigger the same failure.

### 4.1 Deploy-Trigger Hypothesis

**Observation:** The failure often occurs *during* or *shortly after* a deploy. The deploy sequence does several things that can overload a single t3.small node:

| Deploy Phase | What Happens | Potential Impact |
|--------------|--------------|------------------|
| **helm upgrade aws-load-balancer-controller** | Rolling update: 2 old pods → Terminating, 2 new pods → Starting | Old + new LB controller pods coexist briefly; memory spike |
| **kube_apply bootstrap** | Runs Spark bootstrap Job (if not already succeeded) | 1 Spark pod (~512MB–1GB) |
| **kube_apply schedule** | Applies deployment, CronJob; **rollout restart fru-api** | 2 old fru-api → Terminating, 2 new → Starting |
| **CronJob (already running)** | If schedule fired before deploy, 1 Spark Job may be running | 1 Spark pod |

**Concurrent load on 1 node (t3.small, 2GB RAM):**
- 2 fru-api (old Terminating + new Starting) ≈ 1GB
- 2 LB controller (old Terminating + new Starting) ≈ 600MB
- 1 Spark (bootstrap or periodic) ≈ 512MB–1GB
- Daemonsets (aws-node, kube-proxy) ≈ 200MB
- **Total:** 2.3GB+ on a 2GB node → **memory pressure → kubelet stops → node unreachable**

### 4.2 Diagnostic Commands (Run Before Terminating)

When you detect the unreachable failure, capture evidence **before** terminating the node:

```bash
# 1. Node conditions (when did it transition to NotReady?)
kubectl describe node <node-name> | grep -A 30 "Conditions:"

# 2. Recent cluster events (look for NodeNotReady, OOMKilled, Evicted)
kubectl get events -A --sort-by=.lastTimestamp | tail -50

# 3. Pod count and resource usage at time of failure
kubectl get pods -A -o wide | grep -E "fru-kube|kube-system"

# 4. EC2 instance status (from AWS perspective)
# Get instance ID: kubectl get node -o jsonpath='{.items[0].spec.providerID}' | sed 's|.*/||'
aws ec2 describe-instance-status --instance-ids <id> --region <region> --include-all-instances

# 5. EC2 console output (may contain kernel/OOM logs - last ~64KB)
aws ec2 get-console-output --instance-id <id> --region <region> --output text | tail -100
```

### 4.3 What to Look For

| Evidence | Interpretation |
|----------|----------------|
| **Node condition `LastTransitionTime`** | When did Ready→NotReady happen? Correlate with deploy timeline. |
| **`Reason: NodeStatusUnknown`, `Message: Kubelet stopped posting`** | Control plane lost contact; kubelet likely crashed or was starved. |
| **Events: `OOMKilled`, `Evicted`, `Memory pressure`** | Memory exhaustion confirmed. |
| **EC2 status: `running`, system checks `passed`** | Instance is fine; issue is kubelet/application layer. |
| **EC2 console: `Out of memory: Killed process`** | OOM killer killed a process (possibly kubelet or containerd). |

### 4.4 Mitigation Options (Before Next Deploy)

1. **Suspend CronJob before deploy** — Reduces concurrent load during helm upgrade and rollout restart.
2. **Scale to 2 nodes** — `desired_size=2` in EKS node group; workload spreads.
3. **Use t3.medium** — 4GB RAM instead of 2GB; more headroom.
4. **Add resource requests/limits** — Constrain Spark and fru-api so scheduler doesn't overcommit.
5. **Stagger deploy phases** — e.g. wait for LB controller rollout to complete before kube_apply (already done); consider suspending CronJob at start of deploy and re-enabling at end.

---

## 5. References

- [Kubelet stopped posting node status - Karpenter #7029](https://github.com/aws/karpenter-provider-aws/issues/7029)
- [EKS Workshop: Node Not-Ready](https://www.eksworkshop.com/docs/troubleshooting/workernodes/three)
- WAR_STORIES_AWS.md §37 (CronJob AWS credentials)
- WAR_STORIES_CLOUD_SHARED.md §40–41 (CronJob overload cascade, recovery playbook)
