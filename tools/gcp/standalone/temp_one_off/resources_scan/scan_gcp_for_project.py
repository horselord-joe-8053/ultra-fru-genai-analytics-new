#!/usr/bin/env python3
"""
Scan GCP for all resources in a specified project. Project-scoped (service account is project-specific).

Lists: Cloud Run, Cloud Run Jobs, GKE, Artifact Registry, GCS, Cloud SQL, VPC, VPC connectors, Secrets.

Usage:
  python tools/gcp/standalone/temp_one_off/resources_scan/scan_gcp_for_project.py --project fru-proj-1
  python tools/gcp/standalone/temp_one_off/resources_scan/scan_gcp_for_project.py --project fru-proj-1 --region us-central1
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict

# Add project root for imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.cloud_shared.env import load_dotenv

load_dotenv()


def _gcloud_json(cmd: list[str], project: str | None = None) -> dict | list:
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


def _list_names(data: list, name_key: str = "name", metadata_key: str | None = "metadata") -> list[str]:
    """Extract names from gcloud list output."""
    result = []
    for item in data:
        if metadata_key and isinstance(item.get(metadata_key), dict):
            name = item.get(metadata_key, {}).get("name", "")
        else:
            name = item.get(name_key, "")
        if name:
            result.append(name)
    return result


def scan_project(project: str, region: str) -> dict[str, list[str]]:
    """Scan one project for all resource types. Returns {resource_type: [names]}."""
    by_type = defaultdict(list)

    # Cloud Run services
    data = _gcloud_json(["run", "services", "list", f"--region={region}"], project=project)
    if isinstance(data, list):
        by_type["cloud-run"] = _list_names(data, name_key="name", metadata_key="metadata")

    # Cloud Run jobs
    data = _gcloud_json(["run", "jobs", "list", f"--region={region}"], project=project)
    if isinstance(data, list):
        by_type["cloud-run-job"] = _list_names(data, name_key="name", metadata_key="metadata")

    # GKE clusters
    data = _gcloud_json(["container", "clusters", "list", f"--region={region}"], project=project)
    if isinstance(data, list):
        by_type["gke"] = _list_names(data, name_key="name", metadata_key=None)

    # Artifact Registry
    data = _gcloud_json(["artifacts", "repositories", "list", "--location=us-central1"], project=project)
    if isinstance(data, list):
        by_type["artifact-registry"] = [
            r.get("name", "").split("/")[-1] for r in data if r.get("name")
        ]

    # GCS buckets
    data = _gcloud_json(["storage", "buckets", "list"], project=project)
    if isinstance(data, list):
        by_type["gcs"] = _list_names(data, name_key="name", metadata_key=None)

    # Cloud SQL
    data = _gcloud_json(["sql", "instances", "list"], project=project)
    if isinstance(data, list):
        by_type["cloud-sql"] = _list_names(data, name_key="name", metadata_key=None)

    # VPC networks
    data = _gcloud_json(["compute", "networks", "list"], project=project)
    if isinstance(data, list):
        by_type["vpc"] = _list_names(data, name_key="name", metadata_key=None)

    # VPC connectors
    data = _gcloud_json(
        ["compute", "networks", "vpc-access", "connectors", "list", f"--region={region}"],
        project=project,
    )
    if isinstance(data, list):
        by_type["vpc-connector"] = [
            c.get("name", "").split("/")[-1] for c in data if c.get("name")
        ]

    # Secrets
    data = _gcloud_json(["secrets", "list"], project=project)
    if isinstance(data, list):
        by_type["secret"] = [s.get("name", "").split("/")[-1] for s in data if s.get("name")]

    return dict(by_type)


def format_output(project: str, by_type: dict[str, list[str]]) -> str:
    lines = [
        "=" * 80,
        f"GCP Resources in project={project}",
        "=" * 80,
        "",
    ]
    total = 0
    for resource_type in sorted(by_type.keys()):
        items = by_type.get(resource_type, [])
        if items:
            total += len(items)
            lines.append(f"{resource_type}: {len(items)}")
            for item in sorted(items):
                lines.append(f"  - {item}")
            lines.append("")
    lines.insert(3, f"Total: {total} resources")
    lines.insert(4, "")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Scan GCP resources for a project")
    ap.add_argument("--project", required=True, help="GCP project ID")
    ap.add_argument("--region", default="us-central1", help="Region for regional resources")
    args = ap.parse_args()

    print(f"Scanning project={args.project} region={args.region}...", file=sys.stderr)
    by_type = scan_project(args.project, args.region)
    out = format_output(args.project, by_type)
    print(out)


if __name__ == "__main__":
    main()
