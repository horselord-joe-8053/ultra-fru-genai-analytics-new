from tools.cloud_shared.sql.parse_sql_statements import parse_sql_statements


def test_parse_single_statement():
    stmts = parse_sql_statements("SELECT 1;")
    assert len(stmts) == 1
    assert "SELECT 1" in stmts[0]


def test_parse_multiple_and_skip_line_comments():
    sql = """
    -- header
    SELECT 1;
    INSERT INTO t VALUES (1);
    """
    stmts = parse_sql_statements(sql)
    assert len(stmts) == 2


def test_parse_empty():
    assert parse_sql_statements("   ") == []
