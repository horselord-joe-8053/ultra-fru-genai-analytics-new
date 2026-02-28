#!/usr/bin/env python3
"""
Scan GCP for resources in specified project/region, classify into:
  1. Project (FRU) resources - by category (nonkube, durable, nondurable, kube)
  2. Other - resources not matching project prefix/env
  3. Orphans - not in Terraform state (pattern-based)

Uses gcloud commands. Requires gcloud CLI and appropriate project access.

Usage:
  python tools/gcp/standalone/temp_one_off/resources_scan/scan_gcp_remaining.py --project fru-proj-1 --region us-central1
  python tools/gcp/standalone/temp_one_off/resources_scan/scan_gcp_remaining.py --project fru-proj-1 --region us-central1 --env dev --prefix fru
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

# Add project root for imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.cloud_shared.env import load_dotenv

load_dotenv()

# Expected resource patterns from Terraform (tools/gcp/scope_shared/core/resource_names.py)
# nonkube: Cloud Run fru-api-nonkube-dev-us-central1, Spark job fru-dev-spark, CDN bucket
# durable: VPC fru-dev-net, Cloud SQL fru-dev-sql, VPC connector fru-dev-run-conn
# nondurable: GCS delta bucket, Artifact Registry fru-api-img-gcp-dev, fru-spark-img-gcp-dev
# kube: GKE fru-gke-dev-us-central1-a


def _gcloud_json(cmd: list[str], project: str | None = None, region: str | None = None) -> dict | list:
    """Run gcloud, return parsed JSON. Returns {} or [] on failure."""
    full = ["gcloud", "--format=json"] + cmd
    if project:
        full += ["--project", project]
    try:
        out = subprocess.run(full, capture_output=True, text=True, timeout=60)
        if out.returncode == 0 and out.stdout:
            return json.loads(out.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return {} if "list" in " ".join(cmd) else []


@dataclass
class ScanResult:
    project: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    other: list[str] = field(default_factory=list)
    orphans: list[dict] = field(default_factory=list)


def _is_project_resource(name: str, prefix: str, env: str) -> bool:
    """Check if resource name matches project prefix/env pattern."""
    if not prefix or not env:
        return False
    # e.g. fru-api-nonkube-dev-us-central1, fru-dev-net, fru-dev-sql
    return name.startswith(f"{prefix}-") and env in name


def _classify_category(name: str, resource_type: str, prefix: str, env: str) -> str | None:
    """Classify into nonkube, durable, nondurable, kube."""
    if not _is_project_resource(name, prefix, env):
        return None
    if "nonkube" in name or "api" in name and "cloud-run" in resource_type:
        return "nonkube"
    if "gke" in name or "kube" in name:
        return "kube"
    if "net" in name or "sql" in name or "run-conn" in name or "private-ip" in name:
        return "durable"
    if "delta" in name or "img" in name or "artifact" in resource_type:
        return "nondurable"
    return "other"


def scan_cloud_run(project: str, region: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["run", "services", "list", f"--region={region}"], project=project)
    if isinstance(data, list):
        for svc in data:
            name = svc.get("metadata", {}).get("name", "")
            cat = _classify_category(name, "cloud-run", prefix, env)
            if cat:
                r.project[cat].append(f"cloud-run:{name}")
            elif name:
                r.other.append(f"cloud-run:{name}")
    return r


def scan_cloud_run_jobs(project: str, region: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["run", "jobs", "list", f"--region={region}"], project=project)
    if isinstance(data, list):
        for job in data:
            name = job.get("metadata", {}).get("name", "")
            cat = _classify_category(name, "cloud-run-job", prefix, env)
            if cat:
                r.project[cat].append(f"cloud-run-job:{name}")
            elif name:
                r.other.append(f"cloud-run-job:{name}")
    return r


def scan_gke(project: str, region: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["container", "clusters", "list", f"--region={region}"], project=project)
    if isinstance(data, list):
        for c in data:
            name = c.get("name", "")
            cat = _classify_category(name, "gke", prefix, env)
            if cat:
                r.project[cat].append(f"gke:{name}")
            elif name:
                r.other.append(f"gke:{name}")
    return r


def scan_artifact_registry(project: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["artifacts", "repositories", "list", "--location=us-central1"], project=project)
    if isinstance(data, list):
        for repo in data:
            name = repo.get("name", "").split("/")[-1] if repo.get("name") else ""
            if not name:
                continue
            cat = _classify_category(name, "artifact-registry", prefix, env)
            if cat:
                r.project[cat].append(f"artifact-registry:{name}")
            else:
                r.other.append(f"artifact-registry:{name}")
    return r


def scan_gcs_buckets(project: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["storage", "buckets", "list"], project=project)
    if isinstance(data, list):
        for b in data:
            name = b.get("name", "")
            if not name:
                continue
            cat = _classify_category(name, "gcs", prefix, env)
            if cat:
                r.project[cat].append(f"gcs:{name}")
            else:
                r.other.append(f"gcs:{name}")
    return r


def scan_cloud_sql(project: str, region: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["sql", "instances", "list"], project=project)
    if isinstance(data, list):
        for inst in data:
            name = inst.get("name", "")
            if not name:
                continue
            cat = _classify_category(name, "cloud-sql", prefix, env)
            if cat:
                r.project[cat].append(f"cloud-sql:{name}")
            else:
                r.other.append(f"cloud-sql:{name}")
    return r


def scan_vpc_networks(project: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["compute", "networks", "list"], project=project)
    if isinstance(data, list):
        for net in data:
            name = net.get("name", "")
            if not name:
                continue
            if name == "default":
                r.other.append("vpc:default")
                continue
            cat = _classify_category(name, "vpc", prefix, env)
            if cat:
                r.project[cat].append(f"vpc:{name}")
            else:
                r.other.append(f"vpc:{name}")
    return r


def scan_vpc_connectors(project: str, region: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(
        ["compute", "networks", "vpc-access", "connectors", "list", f"--region={region}"],
        project=project,
    )
    if isinstance(data, list):
        for c in data:
            name = c.get("name", "").split("/")[-1] if c.get("name") else ""
            if not name:
                continue
            cat = _classify_category(name, "vpc-connector", prefix, env)
            if cat:
                r.project[cat].append(f"vpc-connector:{name}")
            else:
                r.other.append(f"vpc-connector:{name}")
    return r


def scan_secret_manager(project: str, region: str, prefix: str, env: str) -> ScanResult:
    r = ScanResult()
    data = _gcloud_json(["secrets", "list"], project=project)
    if isinstance(data, list):
        for s in data:
            name = s.get("name", "").split("/")[-1] if s.get("name") else ""
            if not name:
                continue
            cat = _classify_category(name, "secret", prefix, env)
            if cat:
                r.project[cat].append(f"secret:{name}")
            else:
                r.other.append(f"secret:{name}")
    return r


def merge_results(*results: ScanResult) -> ScanResult:
    out = ScanResult()
    for r in results:
        for cat, items in r.project.items():
            out.project[cat].extend(items)
        out.other.extend(r.other)
        out.orphans.extend(r.orphans)
    return out


def format_output(result: ScanResult, prefix: str, env: str) -> str:
    lines = [
        "=" * 80,
        f"GCP Resource Scan (prefix={prefix}, env={env})",
        "=" * 80,
        "",
        "1. PROJECT RESOURCES",
        "=" * 80,
    ]
    for cat in ["nonkube", "durable", "nondurable", "kube", "other"]:
        items = result.project.get(cat, [])
        if items:
            lines.append(f"  [{cat}]")
            for item in sorted(set(items)):
                lines.append(f"    {item}")
    lines.extend(["", "2. OTHER RESOURCES", "=" * 80])
    if result.other:
        for item in sorted(set(result.other))[:50]:
            lines.append(f"  {item}")
        if len(result.other) > 50:
            lines.append(f"  ... and {len(result.other) - 50} more")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Scan GCP resources, classify by project/other")
    ap.add_argument("--project", required=True, help="GCP project ID")
    ap.add_argument("--region", default="us-central1", help="Primary region")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--prefix", default=os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru"))
    args = ap.parse_args()

    project = args.project
    region = args.region
    prefix = args.prefix
    env = args.env

    print(f"Scanning GCP project={project} region={region} (prefix={prefix}, env={env})...", file=sys.stderr)

    results = [
        scan_cloud_run(project, region, prefix, env),
        scan_cloud_run_jobs(project, region, prefix, env),
        scan_gke(project, region, prefix, env),
        scan_artifact_registry(project, prefix, env),
        scan_gcs_buckets(project, prefix, env),
        scan_cloud_sql(project, region, prefix, env),
        scan_vpc_networks(project, prefix, env),
        scan_vpc_connectors(project, region, prefix, env),
        scan_secret_manager(project, region, prefix, env),
    ]
    merged = merge_results(*results)

    out = format_output(merged, prefix, env)
    print(out)


if __name__ == "__main__":
    main()
