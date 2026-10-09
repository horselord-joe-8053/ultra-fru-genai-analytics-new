from tools.cloud_shared.verify.verify_api_endpoints import (
    _integers_in_text,
    _record_count_meets_minimum,
)


def test_record_count_meets_minimum_allows_crud_growth():
    assert _record_count_meets_minimum(201, 200) is True
    assert _record_count_meets_minimum(200, 200) is True
    assert _record_count_meets_minimum(199, 200) is False
    assert _record_count_meets_minimum(None, 200) is False


def test_integers_in_text_finds_count_in_answer():
    text = "The total number of records in the fridge sales database is **201**."
    assert max(_integers_in_text(text)) == 201
