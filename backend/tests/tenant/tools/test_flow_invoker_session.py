"""flow_invoker 护栏：画布工具执行只走 ``short_db_session``，不回退全局会话。

``build_flow_tool_invoker`` 的 ``_invoke`` 在 ``get_worker_session()`` 子树内可达
（Agent 对话 / 定时任务跑画布流程）；Celery 任务每次 ``asyncio.run`` 都是新事件
循环，全局 engine 池里属于上一个 loop 的连接复用即抛
``RuntimeError: ... got Future attached to a different loop``。

本用例把模块命名空间里的全局会话换成「调用即炸」替身，把「不得回退」钉成用例：
一旦有人改回 ``AsyncSessionLocal()``，失败信息会直指该站点，而不是在某个定时任务里
偶发半个失败。``raising=False`` 是有意的——Task 1 之后本模块不再 import
``AsyncSessionLocal``，替换一个「不存在的名字」正是回退可被检出的原因。
"""

from uuid import UUID, uuid4

import pytest

from miles_ai.flow_runtime.types import RunContext
from miles_portal.tenant.tools.services import flow_invoker as invoker_mod
from miles_portal.tenant.tools.services.flow_invoker import build_flow_tool_invoker


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


class _RecordingShortSession:
    """假 short_db_session：交出可辨识的 db，并记录开合次数。"""

    def __init__(self) -> None:
        self.db = object()
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> object:
        self.entered += 1
        return self.db

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


@pytest.mark.asyncio
async def test_flow_tool_invoker_never_falls_back_to_global_session(monkeypatch):
    """工具执行落在短会话上，且 TenantContext / invoke_source 归因不变。"""
    short = _RecordingShortSession()
    monkeypatch.setattr(invoker_mod, "short_db_session", lambda: short, raising=False)
    monkeypatch.setattr(invoker_mod, "AsyncSessionLocal", _Boom(), raising=False)

    seen: list[tuple] = []

    async def fake_invoke(
        db,
        tenant_ctx,
        name,
        params,
        *,
        confirmed,
        actor_user_id,
        agent_id,
        invoke_source,
    ):
        seen.append((db, tenant_ctx, name, params, confirmed, actor_user_id, agent_id, invoke_source))
        return {"result": "ok"}

    monkeypatch.setattr(invoker_mod, "invoke_tool_with_context", fake_invoke)

    tenant_id, user_id, agent_id = uuid4(), uuid4(), uuid4()
    ctx = RunContext(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        agent_id=str(agent_id),
        is_superuser=True,
    )

    out = await build_flow_tool_invoker()("kb_search", {"query": "x"}, ctx, confirmed=True)

    assert out == {"result": "ok"}
    assert (short.entered, short.exited) == (1, 1)
    assert len(seen) == 1
    db, tenant_ctx, name, params, confirmed, actor_user_id, passed_agent_id, invoke_source = seen[0]
    assert db is short.db
    assert name == "kb_search"
    assert params == {"query": "x"}
    assert confirmed is True
    assert tenant_ctx.tenant_id == tenant_id
    assert tenant_ctx.user_id == user_id
    assert tenant_ctx.is_superuser is True
    assert actor_user_id == user_id
    assert passed_agent_id == agent_id
    assert invoke_source == "flow"


@pytest.mark.asyncio
async def test_flow_tool_invoker_absent_ids_fall_back_to_nil_uuid(monkeypatch):
    """无 user_id/agent_id 时仍走短会话，身份降级为 nil uuid / None。"""
    short = _RecordingShortSession()
    monkeypatch.setattr(invoker_mod, "short_db_session", lambda: short, raising=False)
    monkeypatch.setattr(invoker_mod, "AsyncSessionLocal", _Boom(), raising=False)

    seen: list[tuple] = []

    async def fake_invoke(db, tenant_ctx, name, params, *, confirmed, actor_user_id, agent_id, invoke_source):
        seen.append((db, tenant_ctx, actor_user_id, agent_id))
        return {}

    monkeypatch.setattr(invoker_mod, "invoke_tool_with_context", fake_invoke)

    tenant_id = uuid4()
    ctx = RunContext(tenant_id=str(tenant_id))

    out = await build_flow_tool_invoker()("kb_search", {}, ctx, confirmed=False)

    assert out == {}
    db, tenant_ctx, actor_user_id, agent_id = seen[0]
    assert db is short.db
    assert tenant_ctx.tenant_id == tenant_id
    assert tenant_ctx.user_id == UUID(int=0)
    assert actor_user_id == UUID(int=0)
    assert agent_id is None
