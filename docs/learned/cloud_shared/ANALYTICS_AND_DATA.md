# Analytics & Shared Data: Kube vs Nonkube

Content from ANALYTICS_KUBE_NONKUBE_SHARED_DATA with GCP notes.

---

## Overview

Both **Kube** (EKS CronJob / GKE CronJob) and **Nonkube** (ECS EventBridge / Cloud Scheduler) run Spark batch analytics jobs. They share the same data sources and sink.

| Layer | Shared? | Notes |
|-------|---------|-------|
| **Delta table** | Yes | AWS: `s3a://fru-dev-delta-{region}/delta/fru_sales`. GCP: `gs://fru-dev-delta-{region}/delta/fru_sales` |
| **PostgreSQL `batch_analytics`** | Yes | Same Aurora (AWS) or Cloud SQL (GCP) per region; both write to the same table |
| **Per region** | Yes | Each region has its own Delta bucket and DB; see `terra_var_handling.py` region suffix |

## Why Both Panels Show the Same Data

The `/analytics` API reads from `batch_analytics` and returns the latest row. Kube and Nonkube APIs both connect to the same DB instance. The "Updated X ago" timestamp reflects the most recent successful Spark run from **either** environment.

---

## Schedules

| Scope | AWS Trigger | GCP Trigger | Default interval |
|-------|-------------|-------------|------------------|
| **Kube** | CronJob `fru-analytics-periodic-kube` | GKE CronJob | `*/5 * * * *` (every 5 min) |
| **Nonkube** | EventBridge → ECS Spark task | Cloud Scheduler → Cloud Run Job | `rate(1 hour)` / equivalent |

---

## GCP Notes

- **Delta:** GCS bucket per region; Spark uses `gs://` URIs.
- **Cloud SQL:** Same instance for API and Spark; both use VPC connector (nonkube) or GKE private IP (kube).
- **Credentials:** EKS CronJob pods need AWS credentials for S3 (unlike ECS task role). GKE CronJob uses Workload Identity or injected service account for GCS/Cloud SQL.

---

## Decision: Keep Data Centralized

In **PROD**, we deploy either Kube or Nonkube, not both. In **DEV**, both scopes run for learning and as templates. Both writing to the same `batch_analytics` table is acceptable—"last writer wins" is fine for dev.
