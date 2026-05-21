from unittest.mock import patch

from tools.cloud_shared.docker.build_skip_decision import decide_build_skip


def test_decide_build_skip_force_build():
    with patch(
        "tools.cloud_shared.docker.build_skip_decision.compute_build_context_hash",
        return_value="abc123",
    ), patch(
        "tools.cloud_shared.docker.build_skip_decision.get_stored_build_hash",
        return_value="abc123",
    ):
        result = decide_build_skip(
            force_build=True,
            storage_bucket="bucket",
            app_key="app.json",
            spark_key="spark.json",
            provider="local",
        )
    assert result.skip is False
