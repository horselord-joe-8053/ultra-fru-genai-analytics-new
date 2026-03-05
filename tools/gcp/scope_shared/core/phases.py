"""
GCP phase tracking.
Reference: tools/aws/scope_shared/core/phases.py (PhaseTracker, deploy_phases, teardown_phases).
Dynamic phase count and numeration for deploy/teardown/verify.
"""
from typing import Sequence

from tools.aws.scope_shared.core.phases import PhaseTracker


def deploy_phases(scope: str) -> list[str]:
    """Return phase names for GCP deploy (order matches deploy.py). Match AWS flow.
    Ensure secrets runs after durable_with_cooloff and before durable (db_setup job
    needs secret versions to exist)."""
    base = [
        "Doctor checks",
        "State backend bootstrap",
        "Durable-with-cooloff (Secrets)",
        "Ensure secrets",
        "Shared durable (VPC)",
        "Shared nondurable (GCS)",
        "Database setup (pgvector, schema, data)",
        "Build & push images",
    ]
    if scope == "kube":
        return base + ["Kube stack (GKE + frontend)"]
    if scope == "nonkube":
        return base + ["Nonkube stack"]
    if scope == "all":
        return base + ["Nonkube stack", "Kube stack (GKE + frontend)"]
    return base


def teardown_phases(scope: str) -> list[str]:
    """Return phase names for GCP teardown. Dynamic by scope."""
    if scope == "kube":
        return ["Destroy kube stack"]
    if scope == "nonkube":
        return ["Destroy nonkube stack"]
    # scope == "all"
    return [
        "Destroy nonkube stack",
        "Destroy kube stack",
        "Destroy shared-nondurable",
        "Destroy shared-durable",
        "Destroy shared-durable_with_cooloff",
    ]
