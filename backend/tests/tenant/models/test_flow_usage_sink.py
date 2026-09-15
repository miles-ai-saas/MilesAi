"""FlowUsageSink 定向单测：按解析后的模型构造 sink、以 source=flow 落库。

``short_db_session`` 用假 async 上下文管理器替换，不触真实 DB；断言画布用量
不被计入会话 token 累计（source 非 chat）。
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig, ModelUsageLog
from miles_portal.tenant.models.services import usage as usage_mod
from miles_portal.tenant.models.services.usage import (
    begin_chat_usage_accumulation,
    end_chat_usage_accumulation,
    get_chat_usage_totals,
    make_flow_usage_sink_factory,
)


class _FakeSession:
    """假短会话：add 同步收集行，flush/commit 可 await 并计数。"""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.add = Mock(side_effect=self.added.append)
        self.flush_calls = 0
        self.commit_calls = 0

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


class _FakeSessionLocal:
    """假 short_db_session：每次调用返回同一假会话的上下文管理器。"""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self):
        session = self._session

        class _Ctx:
            async def __aenter__(self_inner):
                return session

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


@pytest.mark.asyncio
async def test_flow_usage_sink_records_per_model_with_flow_source(monkeypatch):
    session = _FakeSession()
    monkeypatch.setattr(usage_mod, "short_db_session", _FakeSessionLocal(session))

    tenant_id = uuid4()
    source_id = uuid4()
    model = ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")
    factory = make_flow_usage_sink_factory(tenant_id, source_id=source_id)

    sink = factory(model)
    await sink.record(prompt_tokens=100, completion_tokens=20)

    assert session.flush_calls == 1
    assert session.commit_calls == 1
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, ModelUsageLog)
    assert row.tenant_id == tenant_id
    assert row.model_config_id == model.id
    assert row.source == "flow"
    assert row.source_id == source_id
    assert row.prompt_tokens == 100
    assert row.completion_tokens == 20
    assert row.total_tokens == 120


@pytest.mark.asyncio
async def test_flow_usage_sink_skips_zero_tokens(monkeypatch):
    def _boom():
        raise AssertionError("零用量不应打开会话")

    monkeypatch.setattr(usage_mod, "short_db_session", _boom)
    sink = make_flow_usage_sink_factory(uuid4())(ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x"))
    await sink.record(prompt_tokens=0, completion_tokens=0)


@pytest.mark.asyncio
async def test_flow_usage_sink_does_not_accumulate_chat_tokens(monkeypatch):
    """source=flow 不参与会话 token 累计（累计仅对 chat 生效）。"""
    session = _FakeSession()
    monkeypatch.setattr(usage_mod, "short_db_session", _FakeSessionLocal(session))

    token = begin_chat_usage_accumulation()
    try:
        sink = make_flow_usage_sink_factory(uuid4())(ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x"))
        await sink.record(prompt_tokens=50, completion_tokens=10)
        assert get_chat_usage_totals() == (0, 0)
    finally:
        end_chat_usage_accumulation(token)


@pytest.mark.asyncio
async def test_flow_usage_sink_record_never_falls_back_to_global_session(monkeypatch):
    """``FlowUsageSink.record`` 站点：全局会话换成调用即炸替身，落库仍必须成功。

    ``raising=False`` 是有意的：Task 1 之后本模块不再 import ``AsyncSessionLocal``，
    把一个「不存在的名字」换成替身，正是回退时能被抓到的原因。
    """
    session = _FakeSession()
    monkeypatch.setattr(usage_mod, "short_db_session", _FakeSessionLocal(session), raising=False)
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", _Boom(), raising=False)

    tenant_id = uuid4()
    source_id = uuid4()
    model = ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")
    sink = make_flow_usage_sink_factory(tenant_id, source_id=source_id)(model)

    await sink.record(prompt_tokens=30, completion_tokens=12)

    assert session.flush_calls == 1
    assert session.commit_calls == 1
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, ModelUsageLog)
    assert row.tenant_id == tenant_id
    assert row.model_config_id == model.id
    assert row.source == "flow"
    assert row.source_id == source_id
    assert row.total_tokens == 42
