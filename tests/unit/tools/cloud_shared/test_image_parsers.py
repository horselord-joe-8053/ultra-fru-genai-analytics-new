import tools.cloud_shared.image_registry_tags as tags
import tools.cloud_shared.image_tag as image_tag


def test_parse_container_image():
    assert tags._parse_container_image("repo/app:v1") == ("repo/app", "v1")
    assert tags._parse_container_image("no-tag") is None


def test_parse_gcp_repo_base():
    repo = "us-central1-docker.pkg.dev/myproj/myrepo/app"
    assert tags._parse_gcp_repo_base(repo) == ("myproj", "us-central1", "myrepo")


def test_parse_git_commit_ci():
    assert image_tag._parse_git_commit_ci("2026-03-17 01:39:43 +0800") == ("20260317", image_tag.timedelta(hours=8))


def test_format_tz_suffix_utc():
    assert image_tag._format_tz_suffix(image_tag.timedelta(0)) == "UTC"
