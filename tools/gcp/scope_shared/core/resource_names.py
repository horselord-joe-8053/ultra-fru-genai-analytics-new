"""
GCP resource name assembly.
Reference: tools/aws/scope_shared/core/resource_names.py (naming convention, component defaults).

Naming convention aligned with AWS: {proj}-{component}-{env}-{region}.
- GKE cluster: fru-gke-dev-us-central1 (regional) or fru-gke-dev-us-central1-a (zonal)
- GCS delta bucket: fru-delta-internal-dev-us-central1 (in backend.py)
- Cloud Run service (future): fru-api-nonkube-dev-us-central1
- Cloud Logging: projects/{project}/logs/{log_name}
"""
import os


def _proj_prefix() -> str:
    """Project prefix. PROJ_PREFIX preferred; fallback to FRU_PREFIX."""
    return os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")


def _hyphen(proj: str, component: str, env: str, region: str) -> str:
    """Build hyphen-style name: {proj}-{component}-{env}-{region}."""
    return f"{proj}-{component}-{env}-{region}"


_GKE_CLUSTER_COMPONENT = "gke"
_CLOUD_RUN_SERVICE_COMPONENT = "api-nonkube"
_CLOUD_LOGGING_LOG_SPARK_COMPONENT = "spark"
_K8S_NAMESPACE = "fru-kube"
_SPARK_JOB_COMPONENT = "spark"


def gke_cluster(env: str, region: str, zone: str | None = None) -> str:
    """GKE cluster: {proj}-{component}-{env}-{region} or {zone} when zonal."""
    proj = _proj_prefix()
    comp = os.getenv("GKE_CLUSTER_COMPONENT", "").strip() or _GKE_CLUSTER_COMPONENT
    location = zone if zone else region
    return _hyphen(proj, comp, env, location)


def cloud_run_service(env: str, region: str) -> str:
    """Cloud Run service (nonkube): {proj}-{component}-{env}-{region}."""
    proj = _proj_prefix()
    comp = os.getenv("CLOUD_RUN_SERVICE_COMPONENT", "").strip() or _CLOUD_RUN_SERVICE_COMPONENT
    return _hyphen(proj, comp, env, region)


def log_name_spark(env: str, region: str) -> str:
    """Cloud Logging log name for Spark: {proj}-{component}. Override via CLOUD_LOGGING_LOG_SPARK_COMPONENT."""
    proj = _proj_prefix()
    comp = os.getenv("CLOUD_LOGGING_LOG_SPARK_COMPONENT", "").strip() or _CLOUD_LOGGING_LOG_SPARK_COMPONENT
    return f"{proj}-{comp}"


def k8s_namespace() -> str:
    """K8s namespace (shared with AWS for GKE). Override via K8S_NAMESPACE."""
    return os.getenv("K8S_NAMESPACE", "").strip() or _K8S_NAMESPACE


# Module-level for backward compat (evaluated at import; use k8s_namespace() for late binding)
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "").strip() or _K8S_NAMESPACE

# Artifact Registry (ECR equivalent). Override via ARTIFACT_REGISTRY_*_COMPONENT.
_ARTIFACT_REGISTRY_APP_COMPONENT = "app"
_ARTIFACT_REGISTRY_SPARK_COMPONENT = "spark"


def artifact_registry_repo_app(env: str) -> str:
    """Artifact Registry app repo: {proj}-{component}-{env}."""
    proj = _proj_prefix()
    comp = os.getenv("ARTIFACT_REGISTRY_APP_COMPONENT", "").strip() or _ARTIFACT_REGISTRY_APP_COMPONENT
    return f"{proj}-{comp}-{env}"


def artifact_registry_repo_spark(env: str) -> str:
    """Artifact Registry spark repo: {proj}-{component}-{env}."""
    proj = _proj_prefix()
    comp = os.getenv("ARTIFACT_REGISTRY_SPARK_COMPONENT", "").strip() or _ARTIFACT_REGISTRY_SPARK_COMPONENT
    return f"{proj}-{comp}-{env}"


def spark_job_name(env: str, region: str) -> str:
    """Cloud Run Job name for Spark (periodic): {proj}-{env}-{component}. Override via SPARK_JOB_COMPONENT."""
    proj = _proj_prefix()
    comp = os.getenv("SPARK_JOB_COMPONENT", "").strip() or _SPARK_JOB_COMPONENT
    return f"{proj}-{env}-{comp}"


def db_setup_job_name(env: str, region: str) -> str:
    """Cloud Run Job name for db-setup: {proj}-{env}-db-setup. Separate from main deploy flow."""
    proj = _proj_prefix()
    return f"{proj}-{env}-db-setup"


def cloud_sql_instance(env: str) -> str:
    """Cloud SQL instance name: {proj}-{env}-sql. Matches durable main.tf instance_name."""
    proj = _proj_prefix()
    return f"{proj}-{env}-sql"


def durable_network_name(env: str) -> str:
    """Durable VPC network name: {prefix}-{env}-net. Matches durable main.tf module.vpc name."""
    proj = _proj_prefix()
    return f"{proj}-{env}-net"
