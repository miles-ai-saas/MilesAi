"""run_context 护栏：画布模型解析在自开的一次会话内完成，不占用调用方会话。

``make_flow_model_resolver`` 产出的回调是画布 LLM 节点按 ``model_config_id`` 解析
模型的唯一入口，在 Worker 任务子树内可达（Agent 对话 / 定时任务跑画布流程）。
engine 按事件循环持有（见 ``infra/db/async_session``），Worker 与 API / 脚本因此走
同一条取会话路径。

本用例把模块命名空间里的会话工厂换成假替身，断言解析确实发生在自开的那次会话里。
"""

from uuid import UUID, uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.model import ModelConfig
from miles_portal.tenant.flows.services import run_context as run_context_mod
from miles_portal.tenant.flows.services.run_context import make_flow_model_resolver


class _StubResult:
    """假 Result：``scalar_one_or_none`` 返回预设模型。"""

    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _StubDb:
    """假 AsyncSession：记录 execute 调用并返回预设结果。"""

    def __init__(self, value: object) -> None:
        self._value = value
        self.execute_calls = 0

    async def execute(self, _stmt: object) -> _StubResult:
        self.execute_calls += 1
        return _StubResult(self._value)


class _RecordingShortSession:
    """假 AsyncSessionLocal：交出可辨识的 db，并记录开合次数。"""

    def __init__(self, db: object) -> None:
        self.db = db
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> object:
        self.entered += 1
        return self.db

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


@pytest.mark.asyncio
async def test_model_resolver_runs_inside_its_own_session(monkeypatch):
    """解析命中：查询与 ``resolve_model_for_invoke`` 都发生在自开的那次会话内。"""
    model = ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")
    db = _StubDb(model)
    short = _RecordingShortSession(db)
    monkeypatch.setattr(run_context_mod, "AsyncSessionLocal", lambda: short)

    seen: list[tuple] = []

    async def fake_resolve_model_for_invoke(passed_db, passed_model, passed_tenant_id):
        seen.append((passed_db, passed_model, passed_tenant_id))
        return model

    monkeypatch.setattr(run_context_mod, "resolve_model_for_invoke", fake_resolve_model_for_invoke)

    tenant_id = uuid4()
    resolved = await make_flow_model_resolver(tenant_id)(str(model.id))

    assert resolved is model
    assert db.execute_calls == 1
    assert seen == [(db, model, tenant_id)]
    assert (short.entered, short.exited) == (1, 1)


@pytest.mark.asyncio
async def test_model_resolver_missing_model_reports_bad_request_within_its_own_session(monkeypatch):
    """解析未命中：在自开会话内报「模型配置不存在或已禁用」。"""
    db = _StubDb(None)
    short = _RecordingShortSession(db)
    monkeypatch.setattr(run_context_mod, "AsyncSessionLocal", lambda: short)

    async def _unexpected(*args: object, **kwargs: object) -> object:
        raise AssertionError("未命中模型时不应调用 resolve_model_for_invoke")

    monkeypatch.setattr(run_context_mod, "resolve_model_for_invoke", _unexpected)

    with pytest.raises(BadRequestError, match="模型配置不存在或已禁用"):
        await make_flow_model_resolver(uuid4())(str(UUID(int=7)))

    assert db.execute_calls == 1
    assert (short.entered, short.exited) == (1, 1)
