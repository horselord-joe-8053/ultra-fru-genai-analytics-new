from datetime import datetime, timedelta, timezone

from tools.cloud_shared.analytics_run_status import build_run_status_ui


def test_build_run_status_ui_stale_snapshot():
    old = datetime.now(timezone.utc) - timedelta(minutes=15)
    ui = build_run_status_ui(old, 180, None)
    assert ui["is_stale"] is True
    assert ui["severity"] == "warning"
    assert "Snapshot is" in (ui["status_message"] or "")


def test_build_run_status_ui_shows_last_error():
    old = datetime.now(timezone.utc) - timedelta(minutes=1)
    ui = build_run_status_ui(
        old,
        180,
        {
            "last_error": "ModuleNotFoundError: No module named 'tools'",
            "last_exit_code": 1,
            "last_attempt_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    )
    assert ui["severity"] == "error"
    assert "ModuleNotFoundError" in (ui["status_message"] or "")


def test_build_run_status_ui_ok_when_fresh():
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)
    ui = build_run_status_ui(
        recent,
        180,
        {
            "last_exit_code": 0,
            "last_attempt_at": recent.isoformat().replace("+00:00", "Z"),
        },
    )
    assert ui["severity"] == "ok"
    assert ui["status_message"] is None
