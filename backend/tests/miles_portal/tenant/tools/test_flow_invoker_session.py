"""flow_invoker 护栏：画布工具执行在自开的一次会话内完成，不占用调用方会话。

``build_flow_tool_invoker`` 的 ``_invoke`` 在 Worker 任务子树内可达
（Agent 对话 / 定时任务跑画布流程）；engine 按事件循环持有
（见 ``infra/db/async_session``），故 Worker 与 API / 脚本走同一条取会话路径。

本用例把模块命名空间里的会话工厂换成假替身，断言工具执行确实发生在那次会话里，
而不是借用了别的会话。
"""

from uuid import UUID, uuid4

import pytest

from miles_ai.flow_runtime.types import RunContext
from miles_portal.tenant.tools.services import flow_invoker as invoker_mod
from miles_portal.tenant.tools.services.flow_invoker import build_flow_tool_invoker


class _RecordingShortSession:
    """假 AsyncSessionLocal：交出可辨识的 db，并记录开合次数。"""

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
async def test_flow_tool_invoker_runs_on_its_own_session(monkeypatch):
    """工具执行落在自开的一次会话上，且 TenantContext / invoke_source 归因不变。"""
    short = _RecordingShortSession()
    monkeypatch.setattr(invoker_mod, "AsyncSessionLocal", lambda: short)

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
    """无 user_id/agent_id 时仍自开会话，身份降级为 nil uuid / None。"""
    short = _RecordingShortSession()
    monkeypatch.setattr(invoker_mod, "AsyncSessionLocal", lambda: short)

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
