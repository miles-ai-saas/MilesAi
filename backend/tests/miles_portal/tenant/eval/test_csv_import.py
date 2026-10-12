"""评测用例 CSV 解析。"""

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.eval.services.csv_import import build_expected, parse_eval_cases_csv


def test_parse_eval_cases_csv_basic():
    text = "query,name,expected_mode,expected_value\n退款多久到账,退款,contains,7个工作日\n你好,,exact,你好\n"
    rows = parse_eval_cases_csv(text)
    assert len(rows) == 2
    assert rows[0]["query"] == "退款多久到账"
    assert rows[0]["name"] == "退款"
    assert rows[0]["expected"] == {"contains": "7个工作日"}
    assert rows[1]["expected"] == {"exact": "你好"}


def test_parse_shortcut_columns():
    text = "query,contains\nq1,foo\nq2,\n"
    rows = parse_eval_cases_csv(text)
    assert rows[0]["expected"] == {"contains": "foo"}
    assert rows[1]["expected"] is None


def test_parse_contains_all_pipe():
    text = "query,expected_mode,expected_value\nq,contains_all,a|b|c\n"
    rows = parse_eval_cases_csv(text)
    assert rows[0]["expected"] == {"contains_all": ["a", "b", "c"]}


def test_parse_requires_query_header():
    with pytest.raises(BadRequestError, match="query"):
        parse_eval_cases_csv("name,value\na,b\n")


def test_build_expected_none():
    assert build_expected("none", "x") is None
    assert build_expected("contains", "") is None
