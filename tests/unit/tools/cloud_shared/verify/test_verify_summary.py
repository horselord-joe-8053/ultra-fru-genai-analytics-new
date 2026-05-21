from tools.cloud_shared.verify.verify_summary import VerifyRow, _truncate, _format_row


def test_truncate_no_limit():
    assert _truncate("hello", 0) == "hello"


def test_truncate_with_limit():
    assert _truncate("abcdefghij", 5) == "ab..."


def test_format_row_contains_provider():
    row = VerifyRow(provider="aws", scope="kube", endpoint="health", ok=True, notes="ok")
    line = _format_row(row)
    assert "aws" in line
