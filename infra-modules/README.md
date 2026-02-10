
# Infrastructure Modules

Organized reusable infrastructure-as-code building blocks for multi-cloud deployment.

## Directory Structure

```
infra-modules/
├── shared/                          # Cloud-agnostic components (not provider-specific)
│   ├── primitives/
│   │   └── tags/                    # Common tagging module for all clouds
│   └── k8s/                         # Kubernetes manifests (works on EKS, GKE, AKS, k3s...)
│       ├── api-service.yaml
│       ├── api-deployment.yaml
│       ├── bootstrap-job.yaml
│       └── spark-cronjob.yaml
│
├── aws/                             # AWS-specific modules
│   ├── primitives/                  # AWS cloud primitives
│   │   ├── s3_bucket/               # S3 bucket (object storage)
│   │   └── vpc/                     # VPC with subnets (networking)
│   └── services/                    # Higher-level AWS services
│       ├── ecr/                     # Elastic Container Registry
│       ├── ecs_alb/                 # ECS cluster + ALB
│       └── eks/                     # Elastic Kubernetes Service
│
└── gcp/                             # GCP-specific modules (placeholders)
    └── primitives/                  # GCP cloud primitives
        ├── gcs_bucket/              # Cloud Storage (equivalent to S3)
        └── vpc/                     # VPC (equivalent to AWS VPC)
```

## Module Categories

### Shared (Cloud-Agnostic)
- **tags**: Standard resource tagging (environment, scope, durability labels)
- **k8s**: Kubernetes manifests that run identically on any k8s cluster

### AWS Primitives
- **s3_bucket**: Terraform module for S3 buckets with versioning, encryption, tags
- **vpc**: Terraform module for VPC, subnets, NAT, availability zones, routing

### AWS Services
- **ecr**: Elastic Container Registry for Docker images
- **ecs_alb**: ECS cluster with Application Load Balancer and task definitions
- **eks**: EKS cluster with security groups, node groups, kubeconfig

### GCP Primitives (Placeholders)
- **gcs_bucket**: Cloud Storage bucket (to be implemented)
- **vpc**: VPC network with subnets (to be implemented)

## Usage Pattern

**AWS deployment references AWS primitives:**
```hcl
module "vpc" {
  source = "../../infra-modules/aws/primitives/vpc"
  name   = "my-vpc"
  cidr   = "10.0.0.0/16"
  azs    = ["us-east-1a", "us-east-1b"]
}

module "storage" {
  source = "../../infra-modules/aws/primitives/s3_bucket"
  name   = "my-data-bucket"
  tags   = module.tags.common_tags
}
```

**Kubernetes manifests are cloud-agnostic:**
```bash
kubectl apply -f infra-modules/shared/k8s/api-service.yaml
kubectl apply -f infra-modules/shared/k8s/api-deployment.yaml
```

## Design Philosophy

1. **Separation of concerns**: Cloud-specific logic stays in cloud provider folders
2. **Reusability**: `shared/` modules work identically across providers
3. **Clarity**: Module names map to provider-specific resources (s3_bucket for AWS S3, gcs_bucket for GCP Cloud Storage)
4. **Future-proofing**: Structure ready for multi-cloud without refactoring

## Future: Phase 2 (Not Currently Implemented)

When true multi-cloud abstraction is needed (e.g., same IaC deploying to AWS or GCP):
- Add `shared/interfaces/` with semantic module definitions (storage, registry, network, compute)
- Each cloud provider implements provider-specific modules satisfying the interface
- Deploy scripts select implementation based on cloud provider parameter

**Status**: Not recommended unless actively targeting multiple cloud providers, as it increases complexity significantly.

Modules are environment-agnostic; env/region live in deploy projects.
