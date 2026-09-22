"""ChatUsageSink 自开短会话写入并提交。

生成阶段要释放请求会话连接，前提是用量写入不再挂在调用方事务上。**结构不变量**
（构造签名不含 ``db``，因而不可能持有调用方会话）由
``test_chat_usage_sink_has_no_db_parameter`` 锁定；本文件其余用例只做行为验证：
``record`` 自开短会话、写入并提交一行 ``ModelUsageLog``，字段取自 sink 的构造参数。

**会话来源**另由替身锁定：``record`` 经统一工厂 ``AsyncSessionLocal`` 自开会话
（engine 按事件循环持有，见 ``infra/db/async_session``）；该站点在定时智能体任务里
同样可达（``agent_schedule`` → ``AgentService.chat``）。
"""

import inspect
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig, ModelUsageLog
from miles_portal.tenant.models.services import usage as usage_mod
from miles_portal.tenant.models.services.usage import ChatUsageSink
from tests.miles_portal.tenant.models._usage_doubles import _cm, _ShortSession


def _model() -> ModelConfig:
    return ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")


def test_chat_usage_sink_has_no_db_parameter():
    """结构不变量：不接收调用方会话，就不可能在生成期间抓住它。"""
    assert "db" not in inspect.signature(ChatUsageSink.__init__).parameters


@pytest.mark.asyncio
async def test_record_uses_its_own_session_and_commits(monkeypatch):
    short = _ShortSession()
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", lambda: _cm(short))

    model = _model()
    source_id = uuid4()

    sink = ChatUsageSink(tenant_id=uuid4(), model=model, source_id=source_id)
    await sink.record(prompt_tokens=100, completion_tokens=20)

    assert len(short.rows) == 1
    row = short.rows[0]
    assert isinstance(row, ModelUsageLog)
    assert row.model_config_id == model.id
    assert row.source == "chat"
    assert row.source_id == source_id
    assert short.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt_tokens", "completion_tokens"),
    [(0, 0), (-1, -1), (0, -5)],
)
async def test_record_zero_usage_does_not_open_session(monkeypatch, prompt_tokens, completion_tokens):
    """零/负用量直接返回：连会话都不开，这正是「生成期间不占连接」的最小保证。"""
    short = _ShortSession()
    cm = _cm(short)
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", lambda: cm)

    sink = ChatUsageSink(tenant_id=uuid4(), model=_model(), source_id=uuid4())
    await sink.record(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    assert cm.enters == 0
    assert short.rows == []
    assert short.commits == 0
