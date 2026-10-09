from backend.utils.postgresql_sql import normalize_postgresql_sql


def test_substring_index_rewritten_to_split_part():
    sql = (
        "SELECT SUBSTRING_INDEX(store_address, ',', 2) AS city, SUM(price) AS total "
        "FROM fru_sales_embeddings GROUP BY city;"
    )
    out = normalize_postgresql_sql(sql)
    assert "SUBSTRING_INDEX" not in out.upper()
    assert "SPLIT_PART(store_address, ',', 2)" in out


def test_substring_index_case_insensitive():
    sql = "SELECT substring_index(col, '-', 1) FROM t;"
    out = normalize_postgresql_sql(sql)
    assert "split_part" in out.lower()
    assert "substring_index" not in out.lower()


def test_clean_select_unchanged():
    sql = "SELECT store_name, SUM(price) FROM fru_sales_embeddings GROUP BY store_name;"
    assert normalize_postgresql_sql(sql) == sql


def test_empty_sql_unchanged():
    assert normalize_postgresql_sql("") == ""
