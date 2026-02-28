"""
Configure kubectl for GKE.
Reference: tools/aws/kube/eks_kubeconfig.py (aws eks update-kubeconfig).

Usage:
  python tools/gcp/kube/gke_kubeconfig.py --env dev --region us-central1
"""
import argparse
import os
import subprocess

from tools.cloud_shared.env import load_dotenv
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.gcp.scope_shared.core import resource_names
from tools.gcp.provider_config_handler import get_gke_location

load_dotenv()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    args = ap.parse_args()

    region = resolve_region(args.region)
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project:
        print("Error: GCP_PROJECT_ID must be set", file=__import__("sys").stderr)
        raise SystemExit(1)

    gke_location = get_gke_location(region)
    zone = gke_location if gke_location != region else None
    cluster = resource_names.gke_cluster(args.env, region, zone=zone)

    # Zonal clusters use --zone; regional use --region
    loc_flag = "--zone" if zone else "--region"
    print("+ gcloud container clusters get-credentials")
    subprocess.run(
        [
            "gcloud", "container", "clusters", "get-credentials", cluster,
            loc_flag, gke_location,
            "--project", project,
        ],
        check=True,
        timeout=60,
    )


if __name__ == "__main__":
    main()
