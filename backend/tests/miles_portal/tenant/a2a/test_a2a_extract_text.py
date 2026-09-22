"""``_extract_text_from_response`` 的特征化测试。

该函数解析 A2A 对端返回的 JSON-RPC / HTTP 响应，需兼容多种 result 形状
（text/answer/content/message，以及 message.parts 与 artifacts[].parts），
此前无直接覆盖。

逐层 isinstance 下钻使该函数嵌套达 5 层，重构前先在此锁定每种形状的
取值、键序优先级与兜底行为。
"""

from __future__ import annotations

import pytest

from miles_portal.tenant.a2a.client import _extract_text_from_response


def _fallback(result: object) -> str:
    """复现兜底分支：``str(result)[:4000]``。"""
    return str(result)[:4000]


# --------------------------------------------------------------------------- #
# 非字典输入
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("  hello  ", "hello"),
        ("", ""),
        (123, "123"),
        (None, "None"),
        ([1, 2], "[1, 2]"),
        (True, "True"),
    ],
)
def test_non_dict_input_is_stringified(data, expected):  # noqa: ANN001
    assert _extract_text_from_response(data) == expected


# --------------------------------------------------------------------------- #
# error 优先于 result
# --------------------------------------------------------------------------- #


def test_error_dict_message_wins():
    assert _extract_text_from_response({"error": {"message": "boom"}, "result": "r"}) == "boom"


def test_error_dict_without_message_stringifies_error():
    assert _extract_text_from_response({"error": {"code": 1}}) == str({"code": 1})


def test_error_string_returned_asis():
    assert _extract_text_from_response({"error": "plain"}) == "plain"


# --------------------------------------------------------------------------- #
# result 基本形状
# --------------------------------------------------------------------------- #


def test_result_string_is_stripped():
    assert _extract_text_from_response({"result": "  hi  "}) == "hi"


def test_missing_result_key_falls_back_to_top_level_dict():
    assert _extract_text_from_response({"text": "t"}) == "t"


def test_result_non_dict_non_str_is_stringified():
    assert _extract_text_from_response({"result": 123}) == "123"


@pytest.mark.parametrize("key", ["text", "answer", "content", "message"])
def test_result_string_keys_are_recognized(key):  # noqa: ANN001
    assert _extract_text_from_response({"result": {key: "v"}}) == "v"


def test_result_key_priority_text_before_answer():
    assert _extract_text_from_response({"result": {"text": "t", "answer": "a"}}) == "t"


def test_blank_string_key_is_skipped():
    assert _extract_text_from_response({"result": {"text": "   ", "answer": "a"}}) == "a"


# --------------------------------------------------------------------------- #
# result.message 下钻
# --------------------------------------------------------------------------- #


def test_message_dict_text():
    assert _extract_text_from_response({"result": {"message": {"text": "mt"}}}) == "mt"


def test_message_dict_content():
    assert _extract_text_from_response({"result": {"message": {"content": "mc"}}}) == "mc"


def test_message_dict_parts_first_text():
    assert _extract_text_from_response({"result": {"message": {"parts": [{"text": "mp"}]}}}) == "mp"


def test_message_parts_only_looks_at_first_entry():
    """parts 里有多个元素时只看首项的 text；首项无 text 则整体兜底。"""
    data = {"result": {"message": {"parts": [{"text": ""}, {"text": "second"}]}}}
    assert _extract_text_from_response(data) == _fallback(data["result"])


def test_message_parts_first_entry_without_text_falls_through():
    data = {"result": {"message": {"parts": [{"kind": "x"}]}}}
    assert _extract_text_from_response(data) == _fallback(data["result"])


# --------------------------------------------------------------------------- #
# result.artifacts 下钻
# --------------------------------------------------------------------------- #


def test_artifacts_first_part_text():
    data = {"result": {"artifacts": [{"parts": [{"text": "at"}]}]}}
    assert _extract_text_from_response(data) == "at"


def test_artifacts_empty_parts_falls_through():
    data = {"result": {"artifacts": [{"parts": []}]}}
    assert _extract_text_from_response(data) == _fallback(data["result"])


def test_artifacts_blank_text_falls_through():
    data = {"result": {"artifacts": [{"parts": [{"text": ""}]}]}}
    assert _extract_text_from_response(data) == _fallback(data["result"])


def test_artifacts_only_first_artifact_considered():
    data = {"result": {"artifacts": [{"kind": "z"}, {"parts": [{"text": "second"}]}]}}
    assert _extract_text_from_response(data) == _fallback(data["result"])


# --------------------------------------------------------------------------- #
# 兜底
# --------------------------------------------------------------------------- #


def test_empty_result_dict_falls_back_to_str():
    assert _extract_text_from_response({"result": {}}) == "{}"


def test_fallback_is_truncated_to_4000_chars():
    data = {"result": {"k": "y" * 5000}}
    out = _extract_text_from_response(data)
    assert len(out) == 4000
    assert out == _fallback(data["result"])


def test_long_result_string_is_not_truncated():
    """result 本身是字符串时直接返回，不走 4000 截断。"""
    assert _extract_text_from_response({"result": "z" * 5000}) == "z" * 5000
