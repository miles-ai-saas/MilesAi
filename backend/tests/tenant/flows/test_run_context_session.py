"""run_context 护栏：画布模型解析只走 ``short_db_session``，不回退全局会话。

``make_flow_model_resolver`` 产出的回调是画布 LLM 节点按 ``model_config_id`` 解析
模型的唯一入口，在 ``get_worker_session()`` 子树内可达（Agent 对话 / 定时任务跑画布
流程）。Celery 任务每次 ``asyncio.run`` 都是新事件循环，全局 engine 池里属于上一个
loop 的连接复用即抛 ``RuntimeError: ... got Future attached to a different loop``。

本用例把模块命名空间里的全局会话换成「调用即炸」替身，把「不得回退」钉成用例。
``raising=False`` 是有意的——Task 1 之后本模块不再 import ``AsyncSessionLocal``，
替换一个「不存在的名字」正是回退可被检出的原因。
"""

from uuid import UUID, uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.model import ModelConfig
from miles_portal.tenant.flows.services import run_context as run_context_mod
from miles_portal.tenant.flows.services.run_context import make_flow_model_resolver


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


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
    """假 short_db_session：交出可辨识的 db，并记录开合次数。"""

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
async def test_model_resolver_never_falls_back_to_global_session(monkeypatch):
    """解析命中：查询与 ``resolve_model_for_invoke`` 都发生在短会话内。"""
    model = ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")
    db = _StubDb(model)
    short = _RecordingShortSession(db)
    monkeypatch.setattr(run_context_mod, "short_db_session", lambda: short, raising=False)
    monkeypatch.setattr(run_context_mod, "AsyncSessionLocal", _Boom(), raising=False)

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
async def test_model_resolver_missing_model_reports_bad_request_within_short_session(monkeypatch):
    """解析未命中：在短会话内报「模型配置不存在或已禁用」，不触全局会话。"""
    db = _StubDb(None)
    short = _RecordingShortSession(db)
    monkeypatch.setattr(run_context_mod, "short_db_session", lambda: short, raising=False)
    monkeypatch.setattr(run_context_mod, "AsyncSessionLocal", _Boom(), raising=False)

    async def _unexpected(*args: object, **kwargs: object) -> object:
        raise AssertionError("未命中模型时不应调用 resolve_model_for_invoke")

    monkeypatch.setattr(run_context_mod, "resolve_model_for_invoke", _unexpected)

    with pytest.raises(BadRequestError, match="模型配置不存在或已禁用"):
        await make_flow_model_resolver(uuid4())(str(UUID(int=7)))

    assert db.execute_calls == 1
    assert (short.entered, short.exited) == (1, 1)
