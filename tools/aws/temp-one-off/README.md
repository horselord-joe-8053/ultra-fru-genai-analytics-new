# One-off scripts

Scripts that are run once or rarely (migrations, state imports, troubleshooting), not part of regular deploy/teardown.

- **migrate_state_to_region_key.py** — One-time migration of Terraform state from legacy key to region-scoped key
- **import_state.py** — Import a single resource into Terraform state
- **reconcile_state.py** — Stub; directs to tagging API and import_state.py
- **fix_kube_db_credentials.py** — Fix DB credentials for kube stack when Aurora vs K8s secret mismatch (no full deploy)
- **diagnose_api_db.py** — Diagnose API database and agent connectivity
