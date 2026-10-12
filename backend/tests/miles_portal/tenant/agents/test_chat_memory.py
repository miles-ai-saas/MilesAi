"""服务端对话记忆：截断与加载。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_portal.tenant.agents.services.chat_memory import (
    format_history_block,
    load_chat_history_messages,
    truncate_messages_by_chars,
)


def test_format_history_block_empty():
    assert format_history_block([]) == ""


def test_format_history_block_labels():
    block = format_history_block(
        [
            {"role": "user", "content": "问"},
            {"role": "assistant", "content": "答"},
        ]
    )
    assert "【近期对话】" in block
    assert "用户：问" in block
    assert "助手：答" in block


def test_truncate_keeps_newest_within_budget():
    msgs = [
        {"role": "user", "content": "aaaa"},
        {"role": "assistant", "content": "bbbb"},
        {"role": "user", "content": "cccc"},
    ]
    out = truncate_messages_by_chars(msgs, max_chars=8)
    assert out == [
        {"role": "assistant", "content": "bbbb"},
        {"role": "user", "content": "cccc"},
    ]


def test_truncate_clips_single_overlong_message():
    out = truncate_messages_by_chars(
        [{"role": "user", "content": "0123456789"}],
        max_chars=4,
    )
    assert out == [{"role": "user", "content": "6789"}]


def test_truncate_skips_non_chat_roles():
    out = truncate_messages_by_chars(
        [
            {"role": "system", "content": "sys"},
            {"role": "tool", "content": "tool"},
            {"role": "user", "content": "hi"},
        ],
        max_chars=100,
    )
    assert out == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_load_returns_empty_without_conversation_id():
    db = AsyncMock()
    out = await load_chat_history_messages(
        db,
        tenant_id=uuid4(),
        agent_id=uuid4(),
        conversation_id=None,
    )
    assert out == []
    db.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_returns_empty_on_tenant_mismatch():
    tenant_id, agent_id = uuid4(), uuid4()
    db = AsyncMock()
    db.get = AsyncMock(
        return_value=SimpleNamespace(agent_id=agent_id, tenant_id=uuid4()),
    )
    out = await load_chat_history_messages(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id="sess-1",
        max_chars=100,
        max_messages=10,
    )
    assert out == []


@pytest.mark.asyncio
async def test_load_orders_and_truncates(monkeypatch):
    tenant_id, agent_id = uuid4(), uuid4()
    db = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id))

    # sort_index desc 返回：新 → 旧
    result = MagicMock()
    result.all.return_value = [
        ("user", "cccc"),
        ("assistant", "bbbb"),
        ("user", "aaaa"),
    ]
    db.execute = AsyncMock(return_value=result)

    out = await load_chat_history_messages(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id="sess-1",
        max_chars=8,
        max_messages=10,
    )
    assert out == [
        {"role": "assistant", "content": "bbbb"},
        {"role": "user", "content": "cccc"},
    ]
