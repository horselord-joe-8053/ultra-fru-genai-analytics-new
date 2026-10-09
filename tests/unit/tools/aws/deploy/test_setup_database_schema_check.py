"""Unit tests for AWS setup_database.py schema verification and env passthrough."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[5]
_SETUP = _REPO / "tools/aws/scope_shared/deploy/setup_database.py"


def test_schema_verification_checks_openai_1536_column():
    source = _SETUP.read_text()
    assert "embedding_openai_1536" in source
    assert "column_name='embedding')" not in source


def test_schema_verification_fails_when_column_missing():
    from tools.aws.scope_shared.deploy import setup_database as sd

    rds = MagicMock()
    rds.execute_statement.return_value = {
        "records": [[{"booleanValue": False}]]
    }

    with patch.object(sd, "parse_schema_statements", return_value=[]):
        with patch("backend.services.embedding_sync_rds.apply_migrations_rds"):
            with pytest.raises(RuntimeError, match="embedding_openai_1536"):
                sd.init_schema(rds, "arn:c", "arn:s", "fru_db", force=False)


def test_init_schema_applies_migration_001(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    from tools.aws.scope_shared.deploy import setup_database as sd

    rds = MagicMock()
    rds.execute_statement.return_value = {"records": [[{"booleanValue": True}]]}
    applied = []

    def fake_apply(conn):
        applied.append("migrations")

    with patch.object(sd, "parse_schema_statements", return_value=["CREATE TABLE t;"]):
        with patch("backend.services.embedding_sync_rds.apply_migrations_rds", side_effect=fake_apply):
            sd.init_schema(rds, "arn:c", "arn:s", "fru_db", force=False)

    assert applied == ["migrations"]


def test_load_data_passes_ark_env_to_subprocess(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "ark-secret")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "ep-embed")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example/api/v3")
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("CLOUD_REGION", "us-east-1")

    from tools.aws.scope_shared.deploy import setup_database as sd

    captured = {}

    def fake_run(cmd, env=None, cwd=None, capture_output=None, text=None):
        captured["env"] = env
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch.object(sd.os.path, "exists", return_value=True):
        with patch.object(sd, "get_etl_script_path", return_value=str(tmp_path / "etl.py")):
            with patch.object(sd, "get_csv_path", return_value=str(tmp_path / "data.csv")):
                with patch.object(sd, "get_repo_root", return_value=str(tmp_path)):
                    with patch("boto3.client") as mock_boto_client:
                        mock_boto_client.return_value.execute_statement.return_value = {
                            "records": [[{"longValue": 0}]]
                        }
                        with patch.object(sd.subprocess, "run", side_effect=fake_run):
                            tmp_path.joinpath("etl.py").write_text("# etl")
                            tmp_path.joinpath("data.csv").write_text("id")
                            sd.load_data("dev", "arn:c", "arn:s", "fru_db", force=False)

    assert captured["env"]["ARK_API_KEY"] == "ark-secret"
    assert captured["env"]["ARK_EMBEDDING_MODEL_ID"] == "ep-embed"
    assert captured["env"]["ARK_BASE_URL"] == "https://ark.example/api/v3"


def test_load_data_subprocess_pythonpath_includes_core_app(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("CLOUD_REGION", "us-east-1")

    from tools.aws.scope_shared.deploy import setup_database as sd

    captured = {}

    def fake_run(cmd, env=None, cwd=None, capture_output=None, text=None):
        captured["env"] = env
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    repo = tmp_path
    (repo / "core_app").mkdir()

    with patch.object(sd.os.path, "exists", return_value=True):
        with patch.object(sd, "get_etl_script_path", return_value=str(repo / "etl.py")):
            with patch.object(sd, "get_csv_path", return_value=str(repo / "data.csv")):
                with patch.object(sd, "get_repo_root", return_value=str(repo)):
                    with patch("boto3.client") as mock_boto_client:
                        mock_boto_client.return_value.execute_statement.return_value = {
                            "records": [[{"longValue": 0}]]
                        }
                        with patch.object(sd.subprocess, "run", side_effect=fake_run):
                            repo.joinpath("etl.py").write_text("# etl")
                            repo.joinpath("data.csv").write_text("id")
                            sd.load_data("dev", "arn:c", "arn:s", "fru_db", force=False)

    assert "core_app" in captured["env"]["PYTHONPATH"]
