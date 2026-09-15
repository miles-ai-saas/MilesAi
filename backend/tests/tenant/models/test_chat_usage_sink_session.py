"""ChatUsageSink 自开短会话写入并提交。

生成阶段要释放请求会话连接，前提是用量写入不再挂在调用方事务上。**结构不变量**
（构造签名不含 ``db``，因而不可能持有调用方会话）由
``test_chat_usage_sink_has_no_db_parameter`` 锁定；本文件其余用例只做行为验证：
``record`` 自开短会话、写入并提交一行 ``ModelUsageLog``，字段取自 sink 的构造参数。

**会话来源**另由替身锁定：必须走 ``short_db_session``（Worker 里绑到当前 loop 的
engine），全局 ``AsyncSessionLocal`` 被换成「调用即炸」的替身——``record`` 在定时
智能体任务里同样可达（``agent_schedule`` → ``AgentService.chat``），回退全局会跨
loop 复用池内连接，抛 ``got Future attached to a different loop``。
"""

import inspect
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig, ModelUsageLog
from miles_portal.tenant.models.services import usage as usage_mod
from miles_portal.tenant.models.services.usage import ChatUsageSink
from tests.tenant.models._usage_doubles import _cm, _ShortSession


def _model() -> ModelConfig:
    return ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")


def _boom(*args: object, **kwargs: object) -> None:
    """全局 ``AsyncSessionLocal`` 替身：被调用即炸，让「回退全局」立刻暴露。"""
    raise AssertionError("ChatUsageSink.record 不得用全局 AsyncSessionLocal（Worker 下跨 loop 复用连接必失败）")


def test_chat_usage_sink_has_no_db_parameter():
    """结构不变量：不接收调用方会话，就不可能在生成期间抓住它。"""
    assert "db" not in inspect.signature(ChatUsageSink.__init__).parameters


@pytest.mark.asyncio
async def test_record_uses_its_own_session_and_commits(monkeypatch):
    short = _ShortSession()
    # raising=False：Step 4 前 usage 模块还没有 short_db_session，本用例要能先红在
    # 「走了全局」上（而非红在 monkeypatch 找不到属性），这样才证明护栏真的抓得住回退。
    monkeypatch.setattr(usage_mod, "short_db_session", lambda: _cm(short), raising=False)
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", _boom, raising=False)

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
    monkeypatch.setattr(usage_mod, "short_db_session", lambda: cm, raising=False)
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", _boom, raising=False)

    sink = ChatUsageSink(tenant_id=uuid4(), model=_model(), source_id=uuid4())
    await sink.record(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    assert cm.enters == 0
    assert short.rows == []
    assert short.commits == 0
