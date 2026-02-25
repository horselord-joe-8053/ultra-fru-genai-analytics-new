#!/bin/bash
# Quick check: list ENIs, SGs, and other deps in a VPC that may block deletion.
# Usage: ./check_vpc_enis.sh [vpc-id] [region]
# Uses AWS_PROFILE=admin if not set.
export AWS_PROFILE="${AWS_PROFILE:-admin}"
VPC_ID="${1:-vpc-0951058b8d4fff2e7}"
REGION="${2:-us-east-1}"
echo "=== ENIs in VPC $VPC_ID (region $REGION) ==="
aws ec2 describe-network-interfaces \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --region "$REGION" \
  --query 'NetworkInterfaces[*].[NetworkInterfaceId,Description,Status,InterfaceType,Attachment.InstanceOwnerId,Attachment.AttachmentId]' \
  --output table
echo ""
echo "=== VPC Endpoints in VPC ==="
aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName,VpcEndpointType]' --output table 2>/dev/null || echo "(none or error)"
echo ""
echo "=== Security Groups in VPC (k8s-elb-* = EKS orphan, blocks VPC delete) ==="
aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'SecurityGroups[*].[GroupId,GroupName]' --output table 2>/dev/null || echo "(error)"
echo ""
echo "=== Flow Logs for VPC ==="
aws ec2 describe-flow-logs --filter "Name=resource-id,Values=$VPC_ID" --region "$REGION" --query 'FlowLogs[*].[FlowLogId,LogDestinationType]' --output table 2>/dev/null || echo "(none or error)"
