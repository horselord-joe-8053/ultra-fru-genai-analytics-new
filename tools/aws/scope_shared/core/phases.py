"""
Phase tracking for deploy and teardown. PhaseTracker from cloud_shared; phase lists are AWS-specific.
"""
from tools.cloud_shared.core.phases import PhaseTracker


def deploy_phases(scope: str) -> list[str]:
    """Return phase names for deploy (order matches deploy.py main loop)."""
    shared = [
        "Doctor checks",
        "State backend bootstrap",
        "Durable-with-cooloff (Secrets)",
        "Shared durable (VPC + Aurora)",
        "Shared nondurable (ECR + S3)",
        "Secrets in Secrets Manager",
        "Database setup (pgvector, schema, data)",
        "Build and push images",
        "ECR image URLs",
    ]
    if scope == "all":
        return shared + [
            "Deploy nonkube (ECS + frontend + bootstrap)",
            "Deploy kube (EKS + K8s bootstrap + frontend)",
        ]
    if scope == "kube":
        return shared + ["Apply EKS stack", "K8s bootstrap"]
    # scope == "nonkube"
    return shared + ["Apply ECS stack", "ECS bootstrap"]


def teardown_phases(scope: str) -> list[str]:
    """Return phase names for teardown (order matches teardown scope)."""
    if scope == "kube":
        return ["Destroy kube stack"]
    if scope == "nonkube":
        return ["Destroy nonkube stack"]
    # scope == "all"
    return [
        "Destroy nonkube stack",
        "Destroy kube stack",
        "Destroy shared-nondurable",
    ]
