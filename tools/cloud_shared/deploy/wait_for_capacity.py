"""
Wait-for-capacity helpers for Kubernetes clusters. Provider-agnostic (EKS, GKE).

Used by deploy_kube flows to ensure min_node_count Ready nodes exist before
scheduling heavy workload (helm, kube_apply, rollout). Prevents resource exhaustion
when tofu apply scales the node group but new nodes are not Ready yet.

See docs/TODO_REFACTOR_RESOURCE_CHECK.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import time


def wait_for_kube_nodes_ready(
    min_count: int,
    timeout_seconds: int | None = None,
    interval_seconds: int | None = None,
    region: str | None = None,
) -> None:
    """
    Poll kubectl get nodes until at least min_count nodes are Ready.
    Works for EKS and GKE. Assumes kubeconfig targets the correct cluster.
    Raises TimeoutError if not reached within timeout_seconds.
    """
    timeout_seconds = timeout_seconds or int(os.getenv("KUBE_NODE_WAIT_TIMEOUT_SEC", "600"))
    interval_seconds = interval_seconds or int(os.getenv("KUBE_NODE_WAIT_INTERVAL_SEC", "15"))
    env = {**os.environ}
    if region:
        env["CLOUD_REGION"] = region

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            out = subprocess.check_output(
                ["kubectl", "get", "nodes", "-o", "json"],
                text=True,
                env=env,
                timeout=30,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"kubectl get nodes failed: {e}") from e

        data = json.loads(out)
        ready_count = 0
        for node in data.get("items", []):
            for cond in node.get("status", {}).get("conditions", []):
                if cond.get("type") == "Ready" and cond.get("status") == "True":
                    ready_count += 1
                    break

        if ready_count >= min_count:
            return

        elapsed = time.monotonic() - (deadline - timeout_seconds)
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Expected {min_count} Ready nodes; got {ready_count} after {elapsed:.0f}s. "
                "Nodes may still be booting or unhealthy. Check kubectl get nodes."
            )

        time.sleep(interval_seconds)
