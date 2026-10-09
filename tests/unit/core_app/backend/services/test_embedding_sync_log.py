"""Unit: embedding sync log formatting."""
from backend.services.embedding_sync_core import SyncResult
from backend.services.embedding_sync_log import format_sync_result_detail, format_sync_result_summary


def test_format_sync_result_summary():
    r = SyncResult(
        embedded=400,
        failed=0,
        per_profile={
            "openai_1536": {"embedded": 200, "skipped": 0, "failed": 0},
            "skylark_2048": {"embedded": 200, "skipped": 0, "failed": 0},
        },
    )
    s = format_sync_result_summary(r)
    assert "embedded=400" in s
    assert "openai_1536" in s
    assert "skylark_2048" in s


def test_format_sync_result_detail_lists_errors():
    r = SyncResult(failed=1, errors=["Profile skylark_2048 id F1: embed failed: timeout"])
    lines = format_sync_result_detail(r)
    assert any("error:" in line for line in lines)
    assert any("skylark" in line for line in lines)
