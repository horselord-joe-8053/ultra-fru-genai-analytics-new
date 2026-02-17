
# infra_terraform/live_deploy/aws/scope_shared/durable

Durable shared AWS infra:
- VPC + subnets + NAT
- Base tags
Protected by `prevent_destroy`.

Deploy via:
`python tools/aws/deploy.py --scope kube|nonkube --env dev`
