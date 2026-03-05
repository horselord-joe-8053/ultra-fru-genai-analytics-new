# Deploy Config Schema (Unified)

**Purpose:** Document the structure of `config/cloud/{provider}_deploy_config.yaml`. Both AWS and GCP use the same pattern: `default` block + region-specific overrides, merged by `load_deploy_config(provider, region)`.

## Common Structure

```yaml
default:
  compute: { ... }
  database: { ... }
  network: { ... }  # optional in default

<region_name>:  # e.g. us-east-1, us-central1
  network: { ... }
  compute: { ... }
  database: { ... }
```

## Provider-Specific Keys

| Section   | AWS Keys                         | GCP Keys                                      |
|-----------|-----------------------------------|-----------------------------------------------|
| network   | `azs`, `public_subnet_cidrs`, `private_subnet_cidrs` | `zones`                                       |
| compute   | `desired_nodes`                   | `location_type`, `zone`, `initial_node_count` |
| database  | `multi_az`                        | `high_availability`                            |

## Handler Functions

| Provider | Module                         | Functions                                      |
|----------|--------------------------------|------------------------------------------------|
| AWS      | `tools.aws.provider_config_handler`  | `get_config`, `get_azs`, `get_subnet_cidrs`, `get_compute_config`, `get_database_config` |
| GCP      | `tools.gcp.provider_config_handler`  | `get_config`, `get_gke_location`, `get_initial_node_count`, `get_compute_config`, `get_database_config` |

Both use `load_deploy_config(provider, region)` from `tools.cloud_shared.provider_config_utils`.
