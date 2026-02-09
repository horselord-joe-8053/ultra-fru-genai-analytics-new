
# deploy-aws/shared/durable

Durable shared AWS infra:
- VPC + subnets + NAT
- Base tags
Protected by `prevent_destroy`.

Deploy via:
`python tools/deploy-orchestrator-aws.py --scope kube|nonkube --env dev`
