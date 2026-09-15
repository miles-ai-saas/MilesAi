"""模型用量累计 ContextVar 测试。"""

from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig, ModelUsageLog
from miles_portal.tenant.models.services import usage as usage_mod
from miles_portal.tenant.models.services.usage import (
    ChatUsageSink,
    begin_chat_usage_accumulation,
    end_chat_usage_accumulation,
    get_chat_usage_totals,
)
from tests.tenant.models._usage_doubles import _cm, _ShortSession


def _boom(*args: object, **kwargs: object) -> None:
    """全局 ``AsyncSessionLocal`` 替身：被调用即炸，让「回退全局」立刻暴露。"""
    raise AssertionError("ChatUsageSink.record 不得用全局 AsyncSessionLocal（Worker 下跨 loop 复用连接必失败）")


def test_chat_usage_accumulation():
    token = begin_chat_usage_accumulation()
    try:
        acc = usage_mod._chat_usage_acc.get()
        assert acc is not None
        acc.add(prompt_tokens=120, completion_tokens=30)
        assert get_chat_usage_totals() == (120, 30)
    finally:
        end_chat_usage_accumulation(token)
    assert get_chat_usage_totals() == (0, 0)


@pytest.mark.asyncio
async def test_chat_usage_sink_accumulates_and_commits(monkeypatch):
    short = _ShortSession()
    # 会话来源现在是 short_db_session（Worker 下绑到当前 loop 的 engine）；全局换成
    # 「调用即炸」的替身，任何回退全局的改动都会在这里失败。
    monkeypatch.setattr(usage_mod, "short_db_session", lambda: _cm(short), raising=False)
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", _boom, raising=False)

    begin_chat_usage_accumulation()
    model_id = uuid4()
    source_id = uuid4()
    sink = ChatUsageSink(
        tenant_id=uuid4(),
        model=ModelConfig(id=model_id, name="m", provider="openai", model_name="x"),
        source_id=source_id,
    )
    await sink.record(prompt_tokens=100, completion_tokens=20)

    assert get_chat_usage_totals() == (100, 20)
    row = short.rows[0]
    assert isinstance(row, ModelUsageLog)
    assert row.model_config_id == model_id
    assert row.source == "chat"
    assert row.source_id == source_id
    assert row.prompt_tokens == 100
    assert row.completion_tokens == 20
    assert short.commits == 1
