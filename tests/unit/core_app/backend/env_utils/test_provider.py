from backend.env_utils.cloud_shared.provider import get_cloud_provider


def test_explicit_cloud_provider(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "gcp")
    assert get_cloud_provider() == "gcp"


def test_gcp_from_project_id(monkeypatch):
    monkeypatch.delenv("CLOUD_PROVIDER", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", "my-proj")
    assert get_cloud_provider() == "gcp"


def test_default_local(monkeypatch):
    for key in (
        "CLOUD_PROVIDER",
        "GCP_PROJECT_ID",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "CLOUD_REGION",
        "AWS_ACCESS_KEY_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    assert get_cloud_provider() == "local"
