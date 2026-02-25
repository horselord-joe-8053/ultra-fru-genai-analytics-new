#!/usr/bin/env python3
"""
Scan AWS for ALL resources in specified regions, then classify into:
  0. Orphans - not in Terraform state (definitely / likely, pattern-based rules)
  1. Project (FRU) resources - by category (kube, nonkube, shared-nondurable, shared-durable, other)
  2. Other projects - resources that may incur cost
  3. AWS built-in - AWS-managed, typically no direct cost

Writes orphans to orphan_data/orphans_<YYMMDD-hhmmss>.json for removal/recovery records.

Usage:
  python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py --cloud-regions us-east-1,us-east-2
  python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py --cloud-regions us-east-1,us-east-2 --env dev --prefix fru
  python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py --cloud-regions us-east-1 --env dev --prefix fru --elb  # Classic ELB track

Search criteria (prefix, env) are dynamic from --prefix and --env (or FRU_PREFIX, FRU_ENV).
--elb: Classic ELB track; affects orphan classification for LB/SG/TG (see docs/learned/KUBE_INGRESS_LEARNED.md Section 0).
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.scan.config import (
    FRU_CATEGORIES,
    classify_project_category,
    is_aws_builtin,
    is_project_resource,
)
from tools.aws.scope_shared.scan.orphan_rules import (
    LB_TYPE_CLASSIC,
    classify_orphan,
    get_recovery_hints_for_orphans,
)

load_dotenv()

# CloudFront API is global; AWS requires us-east-1 for CloudFront control plane
_CLOUDFRONT_API_REGION = "us-east-1"

# Directory for orphan JSON output (relative to this script)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ORPHAN_DATA_DIR = os.path.join(_SCRIPT_DIR, "orphan_data")

# Brief hint for S3 only: explains why Terraform state bucket appears in one region.
# Backend (state storage) lives in one region; deploy targets/destinations are in different regions.
_REGION_HINTS: dict[str, str] = {
    "s3": "Storage for various region-specific data",
}


def _region_hint(item: str, region: str) -> str:
    """Return a brief explanation for region-specific resources, else ''."""
    rt = item.split(":")[0] if ":" in item else ""
    hint = _REGION_HINTS.get(rt, "")
    return f" ({hint})" if hint else ""


def _orphan_record(
    resource_type: str,
    name: str,
    display: str,
    region: str | None = None,
    *,
    orphan_note: str = "",
    **extra: str,
) -> dict:
    """Build a structured orphan record for JSON output and removal script."""
    rec: dict = {
        "resource_type": resource_type,
        "name": name,
        "region": region,
        "display": display,
    }
    if orphan_note:
        rec["orphan_note"] = orphan_note
    if extra:
        rec["extra"] = {k: v for k, v in extra.items() if v}
    return rec


@dataclass
class ScanResult:
    """Classified scan results."""

    orphan_definitely: list[dict] = field(default_factory=list)
    orphan_likely: list[dict] = field(default_factory=list)
    project: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))  # category -> items
    other_projects: list[str] = field(default_factory=list)
    aws_builtin: list[str] = field(default_factory=list)


def _aws_json(cmd: list[str], region: str | None = None, env: dict | None = None) -> dict:
    """Run AWS CLI, return parsed JSON. Returns {} on failure."""
    full = ["aws"] + cmd
    if region:
        full += ["--region", region]
    try:
        out = subprocess.run(
            full,
            capture_output=True,
            text=True,
            timeout=30,
            env=env or None,
        )
        if out.returncode == 0 and out.stdout:
            return json.loads(out.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return {}


def _get_account_id() -> str:
    data = _aws_json(["sts", "get-caller-identity"])
    return data.get("Account", "")


def _s3_bucket_region(bucket: str) -> str:
    data = _aws_json(["s3api", "get-bucket-location", "--bucket", bucket])
    loc = data.get("LocationConstraint", "")
    # S3 API: empty LocationConstraint means us-east-1 (AWS convention)
    return loc if loc else "us-east-1"


# -----------------------------------------------------------------------------
# List ALL resources (no prefix filter)
# -----------------------------------------------------------------------------


def _list_all_s3_buckets() -> list[dict]:
    """List ALL S3 buckets. Returns [{name, region}]."""
    data = _aws_json(["s3api", "list-buckets"])
    buckets = data.get("Buckets", [])
    result = []
    for b in buckets:
        name = b.get("Name", "")
        if name:
            region = _s3_bucket_region(name)
            result.append({"name": name, "region": region})
    return result


def _list_all_ecr_repos(region: str) -> list[str]:
    data = _aws_json(["ecr", "describe-repositories", "--region", region])
    return [r.get("repositoryName", "") for r in data.get("repositories", []) if r.get("repositoryName")]


def _list_all_ecs_clusters(region: str) -> list[dict]:
    data = _aws_json(["ecs", "list-clusters", "--region", region])
    arns = data.get("clusterArns", [])
    if not arns:
        return []
    result = []
    for i in range(0, len(arns), 10):
        batch = arns[i : i + 10]
        desc = _aws_json(["ecs", "describe-clusters", "--clusters"] + batch + ["--region", region])
        for c in desc.get("clusters", []):
            name = c.get("clusterName", "")
            if name:
                result.append({"name": name, "status": c.get("status", "")})
    return result


def _list_all_eks_clusters(region: str) -> list[str]:
    data = _aws_json(["eks", "list-clusters", "--region", region])
    return [n for n in data.get("clusters", []) if n]


def _list_all_load_balancers(region: str) -> list[dict]:
    """List ALL load balancers: ELBv2 (ALB + NLB) and Classic ELB. Paginated."""
    result = []
    # ELBv2 (ALB, NLB)
    marker = ""
    while True:
        cmd = ["elbv2", "describe-load-balancers", "--region", region, "--page-size", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd)
        for lb in data.get("LoadBalancers", []):
            name = lb.get("LoadBalancerName", "") or lb.get("LoadBalancerArn", "").split("/")[-1] or "unnamed"
            result.append({
                "name": name,
                "type": lb.get("Type", "unknown"),
                "arn": lb.get("LoadBalancerArn", ""),
                "dns": lb.get("DNSName", ""),
            })
        marker = data.get("NextMarker", "")
        if not marker:
            break
    # Classic ELB (legacy)
    data = _aws_json(["elb", "describe-load-balancers", "--region", region])
    for lb in data.get("LoadBalancerDescriptions", []):
        name = lb.get("LoadBalancerName", "")
        if name:
            result.append({
                "name": name,
                "type": LB_TYPE_CLASSIC,
                "arn": "",
                "dns": lb.get("DNSName", ""),
            })
    return result


def _list_all_target_groups(region: str) -> list[dict]:
    """List ALL target groups. Paginated. Returns [{name, arn}]."""
    marker = ""
    result = []
    while True:
        cmd = ["elbv2", "describe-target-groups", "--region", region, "--page-size", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd)
        for tg in data.get("TargetGroups", []):
            name = tg.get("TargetGroupName", "")
            arn = tg.get("TargetGroupArn", "")
            if name:
                result.append({"name": name, "arn": arn})
        marker = data.get("NextMarker", "")
        if not marker:
            break
    return result


def _list_all_security_groups(region: str) -> list[dict]:
    """List ALL security groups with tags. Returns [{name, group_id, tags_dict}]."""
    data = _aws_json(["ec2", "describe-security-groups", "--region", region])
    result = []
    for sg in data.get("SecurityGroups", []):
        name = sg.get("GroupName", "")
        if name:
            tags = {t.get("Key", ""): t.get("Value", "") for t in sg.get("Tags", [])}
            result.append({
                "name": name,
                "group_id": sg.get("GroupId", ""),
                "tags": tags,
            })
    return result


def _list_all_log_groups(region: str) -> list[str]:
    """List ALL CloudWatch log groups in region (paginated)."""
    token = ""
    result = []
    while True:
        cmd = ["logs", "describe-log-groups", "--region", region, "--limit", "50"]
        if token:
            cmd += ["--next-token", token]
        data = _aws_json(cmd)
        for g in data.get("logGroups", []):
            name = g.get("logGroupName", "")
            if name:
                result.append(name)
        token = data.get("nextToken", "")
        if not token:
            break
    return result


def _list_all_secrets(region: str) -> list[str]:
    data = _aws_json(["secretsmanager", "list-secrets", "--region", region])
    return [s.get("Name", "") for s in data.get("SecretList", []) if s.get("Name")]


def _list_all_ebs_volumes(region: str) -> list[dict]:
    data = _aws_json(["ec2", "describe-volumes", "--region", region])
    result = []
    for v in data.get("Volumes", []):
        vol_id = v.get("VolumeId", "")
        if vol_id:
            tags = {t.get("Key", ""): t.get("Value", "") for t in v.get("Tags", [])}
            result.append({"id": vol_id, "name": tags.get("Name", ""), "state": v.get("State", ""), "tags": tags})
    return result


def _list_all_iam_roles() -> list[str]:
    marker = ""
    result = []
    while True:
        cmd = ["iam", "list-roles", "--max-items", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd)
        for r in data.get("Roles", []):
            name = r.get("RoleName", "")
            if name:
                result.append(name)
        marker = data.get("Marker", "")
        if not marker:
            break
    return result


def _list_all_eventbridge_rules(region: str) -> list[str]:
    data = _aws_json(["events", "list-rules", "--region", region])
    return [r.get("Name", "") for r in data.get("Rules", []) if r.get("Name")]


def _list_all_vpcs(region: str) -> list[str]:
    data = _aws_json(["ec2", "describe-vpcs", "--region", region])
    result = []
    for v in data.get("Vpcs", []):
        for t in v.get("Tags", []):
            if t.get("Key") == "Name":
                name = t.get("Value", "")
                if name:
                    result.append(name)
                break
        else:
            vpc_id = v.get("VpcId", "")
            if vpc_id and vpc_id.startswith("vpc-"):
                result.append(vpc_id)  # unnamed VPC
    return result


def _list_all_rds_clusters(region: str) -> list[str]:
    data = _aws_json(["rds", "describe-db-clusters", "--region", region])
    return [c.get("DBClusterIdentifier", "") for c in data.get("DBClusters", []) if c.get("DBClusterIdentifier")]


def _list_all_cloudfront_distributions() -> list[dict]:
    marker = ""
    result = []
    while True:
        cmd = ["cloudfront", "list-distributions", "--max-items", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd, region=_CLOUDFRONT_API_REGION)
        dist_list = data.get("DistributionList", {})
        for d in dist_list.get("Items") or []:
            result.append({
                "id": d.get("Id", ""),
                "comment": d.get("Comment", "") or "",
                "enabled": d.get("Enabled", False),
                "status": d.get("Status", ""),
            })
        marker = dist_list.get("NextMarker", "")
        if not marker:
            break
    return result


def _list_all_cloudfront_oacs() -> list[dict]:
    """List CloudFront OACs. Returns [{id, name}] for removal/recovery."""
    marker = ""
    result = []
    while True:
        cmd = ["cloudfront", "list-origin-access-controls", "--max-items", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd, _CLOUDFRONT_API_REGION)
        for item in data.get("OriginAccessControlList", {}).get("Items") or []:
            oac_id = item.get("Id", "")
            name = item.get("Name", "")
            if name:
                result.append({"id": oac_id, "name": name})
        marker = data.get("OriginAccessControlList", {}).get("NextMarker", "")
        if not marker:
            break
    return result


# -----------------------------------------------------------------------------
# Scan and classify
# -----------------------------------------------------------------------------


def _classify_and_add(
    result: ScanResult,
    item: str,
    resource_type: str,
    prefix: str,
    env: str,
    region: str = "",
    fmt: str = "",
    *,
    tags: dict[str, str] | None = None,
    lb_type: str = "",
    extra: dict | None = None,
    use_elb: bool = False,
) -> None:
    """Classify a resource and add to the appropriate result bucket."""
    display = fmt or f"{resource_type}:{item}"
    orphan_rt = "load_balancer" if resource_type == "alb" and lb_type else resource_type
    level, note = classify_orphan(
        orphan_rt, item, prefix, env,
        tags=tags, lb_type=lb_type, region=region, use_elb=use_elb,
    )
    ex = dict(extra or {})
    if lb_type:
        ex["lb_type"] = lb_type
    if level == "definitely":
        rec = _orphan_record(
            orphan_rt, item, display,
            region=region or None,
            orphan_note=note,
            **{k: v for k, v in ex.items() if v},
        )
        result.orphan_definitely.append(rec)
        return
    if level == "likely":
        rec = _orphan_record(
            orphan_rt, item, display,
            region=region or None,
            orphan_note=note,
            **{k: v for k, v in ex.items() if v},
        )
        result.orphan_likely.append(rec)
        return
    if is_aws_builtin(display, resource_type):
        result.aws_builtin.append(display)
        return
    if is_project_resource(item, resource_type, prefix, env, region):
        cat = classify_project_category(item, resource_type, prefix, env, region)
        result.project[cat].append(display)
        return
    result.other_projects.append(display)


def scan_region(region: str, prefix: str, env: str, account_id: str, *, use_elb: bool = False) -> ScanResult:
    """Scan one region. List ALL resources, classify each."""
    logger.info(f"[{region}] Scanning ECS, EKS, load balancers, target groups, security groups, log groups, secrets, EBS, EventBridge, VPC, RDS, ECR, S3...")
    result = ScanResult()
    pe = f"{prefix}-{env}"

    # ECS
    for c in _list_all_ecs_clusters(region):
        name = c["name"]
        _classify_and_add(result, name, "ecs_cluster", prefix, env, region, f"ecs_cluster:{name} ({c['status']})")

    # EKS
    for name in _list_all_eks_clusters(region):
        _classify_and_add(result, name, "eks_cluster", prefix, env, region)

    # Load balancers (ALB + NLB + Classic) - paginated, include type and ARN for identification
    for lb in _list_all_load_balancers(region):
        name = lb["name"]
        lb_type = lb.get("type", "")
        arn_suffix = lb.get("arn", "").split(":")[-1] if lb.get("arn") else ""
        display = f"load_balancer:{name} ({lb_type})" + (f" [id={arn_suffix}]" if arn_suffix else "")
        _classify_and_add(result, name, "alb", prefix, env, region, display, lb_type=lb_type, use_elb=use_elb)

    # Target groups
    for tg in _list_all_target_groups(region):
        name = tg["name"]
        arn = tg.get("arn", "")
        display = f"target_group:{name}"
        _classify_and_add(result, name, "target_group", prefix, env, region, display, extra={"target_group_arn": arn}, use_elb=use_elb)

    # Security groups (check orphan first, then k8s cluster ownership)
    cluster_tag = f"kubernetes.io/cluster/{pe}-eks"
    for sg in _list_all_security_groups(region):
        name = sg["name"]
        tags = sg.get("tags", {})
        group_id = sg.get("group_id", "")
        display = f"sg:{name} (k8s cluster {pe}-eks)" if tags.get(cluster_tag) in ("shared", "owned") else f"sg:{name}"
        level, note = classify_orphan("security_group", name, prefix, env, tags=tags, use_elb=use_elb)
        if level == "definitely":
            rec = _orphan_record("security_group", name, display, region=region, orphan_note=note, group_id=group_id)
            result.orphan_definitely.append(rec)
            continue
        if level == "likely":
            rec = _orphan_record("security_group", name, display, region=region, orphan_note=note, group_id=group_id)
            result.orphan_likely.append(rec)
            continue
        if tags.get(cluster_tag) in ("shared", "owned"):
            result.project["kube"].append(display)
            continue
        _classify_and_add(result, name, "security_group", prefix, env, region)

    # Log groups - scan all
    for name in _list_all_log_groups(region):
        if is_aws_builtin(f"log_group:{name}", "log_group"):
            result.aws_builtin.append(f"log_group:{name}")
        elif is_project_resource(name, "log_group", prefix, env, region):
            cat = classify_project_category(name, "log_group", prefix, env, region)
            result.project[cat].append(f"log_group:{name}")
        else:
            result.other_projects.append(f"log_group:{name}")

    # Secrets
    for name in _list_all_secrets(region):
        _classify_and_add(result, name, "secret", prefix, env, region)

    # EBS volumes
    for v in _list_all_ebs_volumes(region):
        tags = v.get("tags", {})
        cluster_tag = f"kubernetes.io/cluster/{pe}-eks"
        name_for_match = tags.get("Name", "") or v["id"]
        is_project = tags.get(cluster_tag) in ("shared", "owned") or pe in name_for_match
        display = f"ebs_volume:{v['id']} ({v['name'] or 'no-name'}) [{v['state']}]"
        if is_project:
            result.project["kube"].append(display)
        elif is_aws_builtin(display, "ebs_volume"):
            result.aws_builtin.append(display)
        else:
            result.other_projects.append(display)

    # EventBridge
    for name in _list_all_eventbridge_rules(region):
        _classify_and_add(result, name, "eventbridge_rule", prefix, env, region)

    # VPC
    for name in _list_all_vpcs(region):
        _classify_and_add(result, name, "vpc", prefix, env, region)

    # RDS
    for name in _list_all_rds_clusters(region):
        _classify_and_add(result, name, "rds_cluster", prefix, env, region)

    # ECR
    for name in _list_all_ecr_repos(region):
        _classify_and_add(result, name, "ecr", prefix, env, region)

    # S3 (filter by region)
    for b in _list_all_s3_buckets():
        if b["region"] != region:
            continue
        name = b["name"]
        if is_aws_builtin(f"s3:{name}", "s3"):
            result.aws_builtin.append(f"s3:{name}")
        elif is_project_resource(name, "s3", prefix, env, region):
            cat = classify_project_category(name, "s3", prefix, env, region)
            result.project[cat].append(f"s3:{name}")
        else:
            result.other_projects.append(f"s3:{name}")

    n_project = sum(len(v) for v in result.project.values())
    n_orphan = len(result.orphan_definitely) + len(result.orphan_likely)
    logger.info(f"[{region}] Done: {n_project} project, {len(result.other_projects)} other, {len(result.aws_builtin)} built-in, {n_orphan} orphans")
    return result


def scan_iam(prefix: str, env: str) -> ScanResult:
    """IAM is global."""
    logger.info("[global] Scanning IAM roles...")
    result = ScanResult()
    for name in _list_all_iam_roles():
        _classify_and_add(result, name, "iam_role", prefix, env, "")
    return result


def scan_cloudfront(prefix: str, env: str) -> ScanResult:
    """CloudFront is global."""
    logger.info("[global] Scanning CloudFront distributions and OACs...")
    result = ScanResult()
    for d in _list_all_cloudfront_distributions():
        comment = d.get("comment", "")
        dist_id = d.get("id", "")
        display = f"cloudfront:{dist_id} ({comment}) [enabled={d['enabled']}, status={d['status']}]"
        if is_project_resource(comment, "cloudfront_dist", prefix, env, ""):
            cat = classify_project_category(comment, "cloudfront_dist", prefix, env, "")
            result.project[cat].append(display)
        elif is_aws_builtin(display, "cloudfront"):
            result.aws_builtin.append(display)
        else:
            result.other_projects.append(display)
    for oac in _list_all_cloudfront_oacs():
        name = oac["name"]
        oac_id = oac.get("id", "")
        display = f"cloudfront_oac:{name}"
        level = classify_orphan("cloudfront_oac", name, prefix, env)
        if level == "definitely":
            rec = _orphan_record("cloudfront_oac", name, display, region=None, oac_id=oac_id)
            result.orphan_definitely.append(rec)
            continue
        if level == "likely":
            rec = _orphan_record("cloudfront_oac", name, display, region=None, oac_id=oac_id)
            result.orphan_likely.append(rec)
            continue
        if is_project_resource(name, "cloudfront_oac", prefix, env, ""):
            cat = classify_project_category(name, "cloudfront_oac", prefix, env, "")
            result.project[cat].append(display)
        elif is_aws_builtin(display, "cloudfront_oac"):
            result.aws_builtin.append(display)
        else:
            result.other_projects.append(display)
    return result


def _write_orphans_json(
    region_results: dict[str, ScanResult],
    iam_result: ScanResult,
    cf_result: ScanResult,
    regions: list[str],
    prefix: str,
    env: str,
) -> str:
    """Write orphans to orphan_data/orphans_<YYMMDD-hhmmss>.json. Returns path."""
    os.makedirs(ORPHAN_DATA_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%y%m%d-%H%M%S")
    path = os.path.join(ORPHAN_DATA_DIR, f"orphans_{ts}.json")

    all_definite: list[dict] = []
    all_likely: list[dict] = []
    for region in regions:
        r = region_results.get(region, ScanResult())
        all_definite.extend(r.orphan_definitely)
        all_likely.extend(r.orphan_likely)
    all_definite.extend(iam_result.orphan_definitely)
    all_definite.extend(cf_result.orphan_definitely)
    all_likely.extend(iam_result.orphan_likely)
    all_likely.extend(cf_result.orphan_likely)

    all_orphans = all_definite + all_likely
    payload = {
        "scan_timestamp": ts,
        "scan_iso": datetime.utcnow().isoformat() + "Z",
        "prefix": prefix,
        "env": env,
        "regions": regions,
        "orphans_definitely": all_definite,
        "orphans_likely": all_likely,
        "recovery_hints": get_recovery_hints_for_orphans(all_orphans),
    }

    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    return path


def format_output(
    regions: list[str],
    region_results: dict[str, ScanResult],
    iam_result: ScanResult,
    cf_result: ScanResult,
    prefix: str,
    env: str,
    *,
    use_elb: bool = False,
) -> str:
    """Format scan results."""
    lines = []
    lb_track = "Classic ELB" if use_elb else "NLB"
    lines.append(f"Scan: regions={', '.join(regions)}, prefix={prefix}, env={env}, kube LB={lb_track}")
    lines.append("")

    # Orphans (not in Terraform state; survive teardown)
    lines.append("=" * 80)
    lines.append("0. ORPHANS (not in Terraform; survive teardown)")
    lines.append("=" * 80)
    all_definite: list[dict] = []
    all_likely: list[dict] = []
    for region in regions:
        r = region_results.get(region, ScanResult())
        all_definite.extend(r.orphan_definitely)
        all_likely.extend(r.orphan_likely)
    all_definite.extend(iam_result.orphan_definitely)
    all_definite.extend(cf_result.orphan_definitely)
    all_likely.extend(iam_result.orphan_likely)
    all_likely.extend(cf_result.orphan_likely)
    if all_definite:
        lines.append("Definitely orphan (pattern-based rules):")
        for rec in sorted(all_definite, key=lambda x: x["display"]):
            note = rec.get("orphan_note", "")
            suffix = f"  # {note}" if note else ""
            lines.append(f"  - {rec['display']}{suffix}")
    if all_likely:
        lines.append("Likely orphan (pattern suggests orphan, not 100%):")
        for rec in sorted(all_likely, key=lambda x: x["display"]):
            note = rec.get("orphan_note", "")
            suffix = f"  # {note}" if note else ""
            lines.append(f"  - {rec['display']}{suffix}")
    if not all_definite and not all_likely:
        lines.append("(none)")
    lines.append("")

    # Summary table: Project resources by category
    lines.append("=" * 80)
    lines.append("1. PROJECT RESOURCES (this project)")
    lines.append("=" * 80)
    col_width = 24
    header = "Region".ljust(col_width) + " | " + " | ".join(c.ljust(col_width) for c in FRU_CATEGORIES)
    lines.append(header)
    lines.append("-" * len(header))
    for region in regions:
        r = region_results.get(region, ScanResult())
        row = [region.ljust(col_width)]
        for cat in FRU_CATEGORIES:
            row.append(str(len(r.project.get(cat, []))).ljust(col_width))
        lines.append(" | ".join(row))
    # Global
    lines.append("(global)".ljust(col_width) + " | " + " | ".join(
        str(len(iam_result.project.get(c, [])) + len(cf_result.project.get(c, []))).ljust(col_width)
        for c in FRU_CATEGORIES
    ))

    # Project detail
    lines.append("")
    lines.append("--- Project detail (per region) ---")
    for region in regions:
        r = region_results.get(region, ScanResult())
        if any(r.project.values()):
            lines.append(f"\n  [{region}]")
            for cat in FRU_CATEGORIES:
                items = r.project.get(cat, [])
                if items:
                    lines.append(f"    [{cat}]")
                    for item in sorted(items):
                        hint = _region_hint(item, region)
                        lines.append(f"      {item}{hint}")
    if any(iam_result.project.values()) or any(cf_result.project.values()):
        lines.append("\n  [global: IAM, CloudFront]")
        for cat in FRU_CATEGORIES:
            items = iam_result.project.get(cat, []) + cf_result.project.get(cat, [])
            if items:
                lines.append(f"    [{cat}]")
                for item in sorted(items):
                    lines.append(f"      {item}")

    # Other projects (cost concern)
    lines.append("")
    lines.append("=" * 80)
    lines.append("2. OTHER PROJECTS (may incur cost)")
    lines.append("=" * 80)
    all_other = []
    for region in regions:
        r = region_results.get(region, ScanResult())
        all_other.extend(r.other_projects)
    all_other.extend(iam_result.other_projects)
    all_other.extend(cf_result.other_projects)
    if all_other:
        lines.append(f"Total: {len(all_other)} resource(s)")
        for item in sorted(set(all_other))[:30]:
            lines.append(f"  - {item}")
        if len(all_other) > 30:
            lines.append(f"  ... and {len(all_other) - 30} more")
    else:
        lines.append("(none)")

    # AWS built-in
    lines.append("")
    lines.append("=" * 80)
    lines.append("3. AWS BUILT-IN (typically no direct cost)")
    lines.append("=" * 80)
    all_builtin = []
    for region in regions:
        r = region_results.get(region, ScanResult())
        all_builtin.extend(r.aws_builtin)
    all_builtin.extend(iam_result.aws_builtin)
    all_builtin.extend(cf_result.aws_builtin)
    if all_builtin:
        lines.append(f"Total: {len(all_builtin)} resource(s)")
        for item in sorted(set(all_builtin))[:20]:
            lines.append(f"  - {item}")
        if len(all_builtin) > 20:
            lines.append(f"  ... and {len(all_builtin) - 20} more")
    else:
        lines.append("(none)")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="Scan AWS for ALL resources, classify into project / other / built-in"
    )
    ap.add_argument("--cloud-regions", required=True, help="Comma-separated regions, e.g. us-east-1,us-east-2")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--prefix", default=os.getenv("FRU_PREFIX", "fru"))
    ap.add_argument("--elb", action="store_true",
        help="Classic ELB track (api-service-elb.yaml). Affects orphan classification for LB/SG/TG.")
    args = ap.parse_args()

    regions = [r.strip() for r in args.cloud_regions.split(",") if r.strip()]
    if not regions:
        logger.error("No regions specified")
        sys.exit(1)

    account_id = _get_account_id()
    if not account_id:
        logger.error("Could not get AWS account ID (check credentials)")
        sys.exit(1)

    logger.step(f"Scanning regions: {', '.join(regions)} (prefix={args.prefix}, env={args.env}, kube LB={'Classic ELB' if args.elb else 'NLB'})")
    region_results: dict[str, ScanResult] = {}
    for region in regions:
        region_results[region] = scan_region(region, args.prefix, args.env, account_id, use_elb=args.elb)

    iam_result = scan_iam(args.prefix, args.env)
    cf_result = scan_cloudfront(args.prefix, args.env)

    n_def = sum(len(r.orphan_definitely) for r in region_results.values()) + len(iam_result.orphan_definitely) + len(cf_result.orphan_definitely)
    n_likely = sum(len(r.orphan_likely) for r in region_results.values()) + len(iam_result.orphan_likely) + len(cf_result.orphan_likely)
    n_proj = sum(sum(len(v) for v in r.project.values()) for r in region_results.values()) + sum(len(v) for v in iam_result.project.values()) + sum(len(v) for v in cf_result.project.values())
    n_other = sum(len(r.other_projects) for r in region_results.values()) + len(iam_result.other_projects) + len(cf_result.other_projects)
    n_builtin = sum(len(r.aws_builtin) for r in region_results.values()) + len(iam_result.aws_builtin) + len(cf_result.aws_builtin)
    logger.info(f"Classified: {n_def} orphans (definitely), {n_likely} orphans (likely), {n_proj} project, {n_other} other, {n_builtin} built-in")

    out = format_output(regions, region_results, iam_result, cf_result, args.prefix, args.env, use_elb=args.elb)
    print(out)

    # Write orphans JSON for removal script and recovery records
    logger.info("Writing orphans to orphan_data/orphans_<ts>.json...")
    json_path = _write_orphans_json(region_results, iam_result, cf_result, regions, args.prefix, args.env)
    logger.success(f"Orphans data written to: {json_path}")


if __name__ == "__main__":
    main()
