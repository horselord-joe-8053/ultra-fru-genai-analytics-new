from tools.cloud_shared.delta_paths import aws_delta_table_path, gcs_delta_table_path


def test_aws_delta_table_path_scoped():
    assert aws_delta_table_path("my-bucket", "kube") == "s3a://my-bucket/delta/kube/fru_sales"
    assert aws_delta_table_path("my-bucket", "nonkube") == "s3a://my-bucket/delta/nonkube/fru_sales"


def test_gcs_delta_table_path_scoped():
    assert gcs_delta_table_path("my-bucket", "kube") == "gs://my-bucket/delta/kube/fru_sales"
