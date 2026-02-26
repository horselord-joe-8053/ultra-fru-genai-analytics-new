#!/usr/bin/env bash
# DEPRECATED: Use install_aws_load_balancer_controller.py instead (cross-platform, integrated into deploy).
# This script is kept for reference; deploy runs the Python version automatically.
#
# Install AWS Load Balancer Controller on EKS.
# Required for fru-api-svc with aws-load-balancer-type: external (NLB instead of Classic ELB).
#
# Usage:
#   ./tools/aws/kube/install_aws_load_balancer_controller.sh [--env dev] [--region us-east-1] [--profile PROFILE]
#
# Or use AWS_PROFILE env:
#   AWS_PROFILE=myprofile ./tools/aws/kube/install_aws_load_balancer_controller.sh --env dev
#
# Prerequisites: eksctl, helm, kubectl, AWS credentials, kubeconfig pointing at the cluster.

set -e

ENV="${ENV:-dev}"
REGION="${REGION:-us-east-1}"
PREFIX="${PROJ_PREFIX:-${FRU_PREFIX:-fru}}"
PROFILE="${AWS_PROFILE:-}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)     ENV="$2"; shift 2 ;;
    --region)  REGION="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# New format: {prefix}-{component}-{env}-{region}; matches resource_names.eks_cluster()
EKS_COMPONENT="${EKS_CLUSTER_COMPONENT:-eks}"
CLUSTER_NAME="${PREFIX}-${EKS_COMPONENT}-${ENV}-${REGION}"
[[ -n "$PROFILE" ]] && export AWS_PROFILE="$PROFILE"

echo "Installing AWS Load Balancer Controller for cluster=${CLUSTER_NAME} region=${REGION}${PROFILE:+ profile=${PROFILE}}"

# 1. Ensure OIDC provider (EKS Terraform may create it; eksctl adds if missing)
eksctl utils associate-iam-oidc-provider --cluster="$CLUSTER_NAME" --region="$REGION" --approve || true

# 2. Create IAM policy if not exists
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy"
if ! aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
  echo "Creating IAM policy AWSLoadBalancerControllerIAMPolicy..."
  curl -sLo /tmp/iam-policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v3.0.0/docs/install/iam_policy.json
  aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file:///tmp/iam-policy.json
fi
echo "Using policy: $POLICY_ARN"

# 3. Create IAM role + ServiceAccount
eksctl create iamserviceaccount \
  --cluster="$CLUSTER_NAME" \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn="$POLICY_ARN" \
  --override-existing-serviceaccounts \
  --region="$REGION" \
  --approve

# 4. Add Helm repo and install controller
helm repo add eks https://aws.github.io/eks-charts 2>/dev/null || true
helm repo update

# Get VPC ID (avoids IMDS lookup; fixes CrashLoopBackOff on IMDSv2-restricted nodes)
VPC_ID=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" --query 'cluster.resourcesVpcConfig.vpcId' --output text 2>/dev/null || true)

helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName="$CLUSTER_NAME" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region="$REGION" \
  $([ -n "$VPC_ID" ] && echo "--set vpcId=$VPC_ID" || true)

echo "Waiting for controller pods..."
kubectl wait --for=condition=available --timeout=120s \
  deployment/aws-load-balancer-controller -n kube-system 2>/dev/null || true

kubectl get deployment -n kube-system aws-load-balancer-controller
echo "Done. The controller will reconcile fru-api-svc and create an NLB."
