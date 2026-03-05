"""
Orphan cleanup for teardown.

EKS cluster/node SGs: Created by AWS as side effects of aws_eks_cluster and
aws_eks_node_group (not Terraform resources). AWS does not always delete them
when the cluster is removed. Post-destroy CLI cleanup is the common industry
practice. See docs/war_stories/WAR_STORIES_AWS.md ##23.

k8s-elb-* SGs: In-tree cloud provider creates these when a Classic ELB Service
(type LoadBalancer without aws-load-balancer-type) is applied. When we kubectl
delete the Service, the ELB is removed but the k8s-elb-* SG is orphaned. It
blocks VPC deletion until removed. Must run after kube destroy, before durable.
"""
import json
import os
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats

# Retry for k8s-elb-* SG: ENI release after LB delete is async (10–30 min)
K8S_ELB_SG_WAIT_TIMEOUT_SEC = int(os.environ.get("K8S_ELB_SG_WAIT_TIMEOUT_SEC", "300"))
K8S_ELB_SG_POLL_INTERVAL_SEC = int(os.environ.get("K8S_ELB_SG_POLL_INTERVAL_SEC", "30"))


def remove_orphaned_k8s_elb_security_groups(
    env: str,
    region: str | None = None,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Remove orphaned k8s-elb-* security groups (post kube destroy, pre durable).

    In-tree creates these when Classic ELB Service exists. kubectl delete svc
    removes the ELB but not the SG. The SG blocks VPC deletion. Run after kube
    stack destroy, before durable. Retries on DependencyViolation (ENI release).
    """
    from tools.cloud_shared.logging import logger
    from tools.aws.scope_shared.core.backend import resolve_region

    region = region or resolve_region(None)

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    def _remove():
        out = subprocess.run(
            [
                "aws", "ec2", "describe-security-groups",
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
            all_sgs = json.loads(out.stdout or "[]")
        except json.JSONDecodeError:
            return
        sgs = [s for s in all_sgs if (s.get("Name") or "").startswith("k8s-elb-")]
        if not sgs:
            return

        for sg in sgs:
            sg_id = sg.get("Id")
            sg_name = sg.get("Name", sg_id)
            if not sg_id:
                continue
            start = time.monotonic()
            deadline = start + K8S_ELB_SG_WAIT_TIMEOUT_SEC
            while time.monotonic() < deadline:
                r = subprocess.run(
                    ["aws", "ec2", "delete-security-group", "--group-id", sg_id, "--region", region],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if r.returncode == 0:
                    logger.info(f"Removed orphaned k8s-elb-* security group: {sg_name}")
                    break
                if "DependencyViolation" not in (r.stderr or "") and "dependent object" not in (r.stderr or "").lower():
                    logger.warning(f"Failed to delete {sg_name}: {r.stderr or r.stdout}")
                    break
                elapsed = int(time.monotonic() - start)
                logger.info(
                    f"Waiting for {sg_name} to become deletable (ENI release after LB delete, can take 10–30 min) ... ({elapsed}s)"
                )
                time.sleep(K8S_ELB_SG_POLL_INTERVAL_SEC)

    _timed("k8s-elb-* security groups (post kube)", region, _remove)


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
    common industry practice. Idempotent. See docs/war_stories/WAR_STORIES_AWS.md ##23.
    """
    from tools.cloud_shared.logging import logger

    from tools.aws.scope_shared.core.backend import resolve_region
    region = region or resolve_region(None)
    from tools.aws.scope_shared.core import resource_names
    cluster_name = resource_names.eks_cluster(env, region)
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
