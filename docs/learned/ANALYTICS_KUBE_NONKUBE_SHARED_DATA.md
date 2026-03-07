# Analytics: Kube vs Nonkube Shared Data

## Overview

Both **Kube** (EKS CronJob) and **Nonkube** (ECS EventBridge) run Spark batch analytics jobs. They share the same data sources and sink.

| Layer | Shared? | Notes |
|-------|---------|-------|
| **S3 Delta table** | Yes | Same path per region (e.g. `s3a://fru-dev-delta-us-east-1/delta/fru_sales`) |
| **PostgreSQL `batch_analytics`** | Yes | Same Aurora instance per region; both write to the same table |
| **Per region** | Yes | Each region has its own Delta bucket and Aurora; see `terra_var_handling.py` region suffix |

## Why Both Panels Show the Same Data

The `/analytics` API reads from `batch_analytics` and returns the latest row. Kube and Nonkube APIs both connect to the same Aurora instance. The "Updated X ago" timestamp reflects the most recent successful Spark run from **either** environment.

## Schedules

| Scope | Trigger | Default interval |
|-------|---------|------------------|
| **Kube** | CronJob `fru-analytics-periodic-kube` | `*/5 * * * *` (every 5 min) |
| **Nonkube** | EventBridge → ECS Spark task | `rate(1 hour)` |

## Decision: Keep Data Centralized

In **PROD**, we deploy either Kube or Nonkube, not both. In **DEV**, both scopes run for learning and as templates. Both writing to the same `batch_analytics` table is acceptable — "last writer wins" is fine for dev.

See **War Story 63** in [docs/war_stories/WAR_STORIES_CLOUD_SHARED.md](../war_stories/WAR_STORIES_CLOUD_SHARED.md) for the CronJob credentials fix and full context.
