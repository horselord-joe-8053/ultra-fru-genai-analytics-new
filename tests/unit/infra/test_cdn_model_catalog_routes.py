"""CDN / edge modules must route /model-catalog to the API origin (not static SPA)."""

from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]


def test_aws_cloudfront_routes_model_catalog_to_api():
    text = (_REPO / "infra_terraform/modules/aws/primitives/cloudfront/main.tf").read_text(
        encoding="utf-8"
    )
    assert 'path_pattern     = "/model-catalog"' in text


def test_gcp_cloud_cdn_routes_model_catalog_to_api():
    text = (_REPO / "infra_terraform/modules/gcp/primitives/cloud_cdn/main.tf").read_text(
        encoding="utf-8"
    )
    assert "/model-catalog" in text
