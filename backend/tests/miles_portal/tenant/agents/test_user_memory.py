"""跨会话用户记忆：格式化与 JSON 解析。"""

from types import SimpleNamespace

from miles_portal.tenant.agents.services.user_memory import format_long_term_block, user_memory_enabled
from miles_portal.tenant.agents.services.user_memory_extract import parse_memory_json


def test_user_memory_enabled():
    assert user_memory_enabled(SimpleNamespace(config={"user_memory": {"enabled": True}})) is True
    assert user_memory_enabled(SimpleNamespace(config={"user_memory": {"enabled": False}})) is False
    assert user_memory_enabled(SimpleNamespace(config={})) is False


def test_format_long_term_block():
    rows = [
        SimpleNamespace(kind="preference", content="喜欢简洁回答"),
        SimpleNamespace(kind="summary", content="经常询问订单状态"),
    ]
    text = format_long_term_block(rows, max_chars=2000)
    assert "【关于该用户的长期记忆】" in text
    assert "偏好" in text
    assert "摘要" in text


def test_format_long_term_block_empty():
    assert format_long_term_block([], max_chars=100) == ""
    assert format_long_term_block([SimpleNamespace(kind="summary", content="  ")], max_chars=100) == ""


def test_parse_memory_json():
    raw = '{"summary":"用户关注物流","preference":"中文回复"}'
    assert parse_memory_json(raw) == {"summary": "用户关注物流", "preference": "中文回复"}
    assert parse_memory_json('{"summary":"","preference":"简洁"}') == {"summary": "", "preference": "简洁"}
    assert parse_memory_json("not json") == {}
