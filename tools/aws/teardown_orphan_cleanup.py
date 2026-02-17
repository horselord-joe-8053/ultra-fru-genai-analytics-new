"""
Orphan cleanup for teardown.

EKS cluster/node SGs: Created by AWS as side effects of aws_eks_cluster and
aws_eks_node_group (not Terraform resources). AWS does not always delete them
when the cluster is removed. Post-destroy CLI cleanup is the common industry
practice. See README_WAR_STORIES ##41.
"""
import json
import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.aws.teardown_stats import TeardownStats


def remove_orphaned_eks_security_groups(
    env: str,
    region: str | None = None,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Remove orphaned EKS cluster and node security groups when cluster is gone.

    These SGs are created by AWS (not Terraform) when aws_eks_cluster and
    aws_eks_node_group are applied. AWS does not always delete them on cluster
    destroy. Terraform has no state for them—post-destroy CLI cleanup is the
    common industry practice. Idempotent. See README_WAR_STORIES ##41.
    """
    from tools.common.logging import logger

    region = region or os.getenv("CLOUD_REGION", os.getenv("AWS_REGION", "us-east-1"))
    cluster_name = os.getenv("EKS_CLUSTER_NAME") or f"{os.getenv('FRU_PREFIX', 'fru')}-{env}-eks"
    nodes_sg_name = f"{cluster_name}-nodes-sg"
    cluster_sg_name = f"{cluster_name}-cluster-sg"

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    # If cluster exists, Terraform destroy will remove it; skip (SGs deleted with cluster or orphaned later)
    out = subprocess.run(
        ["aws", "eks", "describe-cluster", "--name", cluster_name, "--region", region],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode == 0:
        return  # Cluster exists; Terraform handles cleanup

    def _remove_sgs():
        # Find SG IDs by name
        out = subprocess.run(
            [
                "aws", "ec2", "describe-security-groups",
                "--filters", f"Name=group-name,Values={nodes_sg_name},{cluster_sg_name}",
                "--region", region,
                "--query", "SecurityGroups[*].{Name:GroupName,Id:GroupId}",
                "--output", "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode != 0:
            return
        try:
            sgs = json.loads(out.stdout or "[]")
        except json.JSONDecodeError:
            return
        if not sgs:
            return

        sg_by_name = {s["Name"]: s["Id"] for s in sgs}
        nodes_sg_id = sg_by_name.get(nodes_sg_name)
        cluster_sg_id = sg_by_name.get(cluster_sg_name)

        if not nodes_sg_id or not cluster_sg_id:
            return

        # Revoke mutual rules (nodes-sg ingress from cluster-sg; cluster-sg egress to nodes-sg)
        for group_id, peer_id, direction in [
            (nodes_sg_id, cluster_sg_id, "ingress"),
            (cluster_sg_id, nodes_sg_id, "egress"),
        ]:
            perm = {
                "IpProtocol": "tcp",
                "FromPort": 1025,
                "ToPort": 65535,
                "UserIdGroupPairs": [{"GroupId": peer_id}],
            }
            if direction == "ingress":
                subprocess.run(
                    ["aws", "ec2", "revoke-security-group-ingress", "--group-id", group_id, "--region", region, "--ip-permissions", json.dumps([perm])],
                    capture_output=True,
                    check=False,
                )
            else:
                subprocess.run(
                    ["aws", "ec2", "revoke-security-group-egress", "--group-id", group_id, "--region", region, "--ip-permissions", json.dumps([perm])],
                    capture_output=True,
                    check=False,
                )

        # Delete nodes-sg first, then cluster-sg
        for sg_id, name in [(nodes_sg_id, nodes_sg_name), (cluster_sg_id, cluster_sg_name)]:
            r = subprocess.run(
                ["aws", "ec2", "delete-security-group", "--group-id", sg_id, "--region", region],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                logger.info(f"Removed orphaned EKS security group: {name}")

    _timed("EKS security groups (orphan cleanup)", cluster_name, _remove_sgs)
