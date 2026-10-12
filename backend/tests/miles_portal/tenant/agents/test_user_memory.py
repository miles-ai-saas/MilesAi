"""跨会话用户记忆：格式化、配置与相关性排序。"""

from types import SimpleNamespace
from uuid import uuid4

from miles_portal.tenant.agents.services.user_memory import (
    cosine_similarity,
    format_long_term_block,
    rank_memories_for_query,
    user_memory_enabled,
    user_memory_recall_mode,
    user_memory_scope,
)
from miles_portal.tenant.agents.services.user_memory_extract import parse_memory_json


def test_user_memory_enabled():
    assert user_memory_enabled(SimpleNamespace(config={"user_memory": {"enabled": True}})) is True
    assert user_memory_enabled(SimpleNamespace(config={"user_memory": {"enabled": False}})) is False
    assert user_memory_enabled(SimpleNamespace(config={})) is False


def test_user_memory_scope_and_recall():
    assert user_memory_scope(SimpleNamespace(config={})) == "per_agent"
    assert user_memory_scope(SimpleNamespace(config={"user_memory": {"scope": "tenant_user"}})) == "tenant_user"
    assert user_memory_scope(SimpleNamespace(config={"user_memory": {"scope": "weird"}})) == "per_agent"
    assert user_memory_recall_mode(SimpleNamespace(config={})) == "all"
    assert (
        user_memory_recall_mode(SimpleNamespace(config={"user_memory": {"recall_mode": "relevant"}}))
        == "relevant"
    )


def test_format_long_term_block():
    rows = [
        SimpleNamespace(kind="preference", content="喜欢简洁回答", agent_id=uuid4()),
        SimpleNamespace(kind="summary", content="经常询问订单状态", agent_id=uuid4()),
    ]
    text = format_long_term_block(rows, max_chars=2000)
    assert "【关于该用户的长期记忆】" in text
    assert "偏好" in text
    assert "摘要" in text


def test_format_long_term_block_with_agent_labels():
    aid = uuid4()
    rows = [SimpleNamespace(kind="preference", content="简洁", agent_id=aid)]
    text = format_long_term_block(rows, max_chars=2000, agent_labels={str(aid): "客服助手"})
    assert "偏好（客服助手）" in text


def test_format_long_term_block_empty():
    assert format_long_term_block([], max_chars=100) == ""
    assert format_long_term_block([SimpleNamespace(kind="summary", content="  ")], max_chars=100) == ""


def test_cosine_and_rank():
    assert abs(cosine_similarity([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    a = SimpleNamespace(kind="summary", content="order logistics status", content_embedding=[1.0, 0.0])
    b = SimpleNamespace(kind="preference", content="prefers concise replies", content_embedding=[0.0, 1.0])
    ranked = rank_memories_for_query([a, b], query="logistics", query_embedding=[1.0, 0.0])
    assert ranked[0] is a
    by_kw = rank_memories_for_query([a, b], query="concise replies please")
    assert by_kw[0] is b


def test_parse_memory_json():
    raw = '{"summary":"用户关注物流","preference":"中文回复"}'
    assert parse_memory_json(raw) == {"summary": "用户关注物流", "preference": "中文回复"}
    assert parse_memory_json('{"summary":"","preference":"简洁"}') == {"summary": "", "preference": "简洁"}
    assert parse_memory_json("not json") == {}
