"""Scope-scoped Delta table paths (kube vs nonkube) to avoid concurrent overwrites in dev."""


def delta_table_path_uri(
    bucket_uri_prefix: str,
    deploy_scope: str,
    table_name: str = "fru_sales",
) -> str:
    """
    Build per-scope Delta table URI.

    bucket_uri_prefix: e.g. s3a://my-bucket or gs://my-bucket
    deploy_scope: nonkube | kube | local scope label
    """
    scope = (deploy_scope or "nonkube").strip().lower()
    base = bucket_uri_prefix.rstrip("/")
    return f"{base}/delta/{scope}/{table_name}"


def aws_delta_table_path(bucket: str, deploy_scope: str) -> str:
    return delta_table_path_uri(f"s3a://{bucket}", deploy_scope)


def gcs_delta_table_path(bucket: str, deploy_scope: str) -> str:
    return delta_table_path_uri(f"gs://{bucket}", deploy_scope)
