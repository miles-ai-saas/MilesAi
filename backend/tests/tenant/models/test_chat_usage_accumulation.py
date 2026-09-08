"""模型用量累计 ContextVar 测试。"""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.model import ModelConfig
from app.tenant.models.services import usage as usage_mod
from app.tenant.models.services.usage import (
    ChatUsageSink,
    begin_chat_usage_accumulation,
    end_chat_usage_accumulation,
    get_chat_usage_totals,
)


@pytest.fixture
async def db_session():
    """无真实 DB 的 AsyncSession 替身：add 同步接收行，flush 可 await。"""
    session = AsyncMock()
    session.add = Mock()
    return session


def test_chat_usage_accumulation():
    token = begin_chat_usage_accumulation()
    try:
        usage_mod._chat_usage_acc.set((120, 30))
        assert get_chat_usage_totals() == (120, 30)
    finally:
        end_chat_usage_accumulation(token)
    assert get_chat_usage_totals() == (0, 0)


@pytest.mark.asyncio
async def test_chat_usage_sink_accumulates_and_flushes(db_session):
    begin_chat_usage_accumulation()
    sink = ChatUsageSink(
        db=db_session,
        tenant_id=uuid4(),
        model=ModelConfig(name="m", provider="openai", model_name="x"),
        source_id=uuid4(),
    )
    await sink.record(prompt_tokens=100, completion_tokens=20)
    assert get_chat_usage_totals() == (100, 20)
    db_session.add.assert_called_once()
