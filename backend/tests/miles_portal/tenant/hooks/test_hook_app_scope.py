"""HookScope.APP：安装记录解析与 run_resource 外包顺序。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services import app_scope as app_scope_mod
from miles_portal.tenant.hooks.services.result import HookRunResult
from miles_portal.tenant.hooks.services.runner import HookRunner


@pytest.mark.asyncio
async def test_resolve_install_app_id_by_agent(monkeypatch):  # noqa: ANN001
    tenant_id = uuid4()
    agent_id = uuid4()
    app_id = uuid4()

    class _Result:
        def scalar(self):
            return app_id

    class _Db:
        async def scalar(self, _stmt):  # noqa: ANN001
            return app_id

        async def execute(self, _stmt):  # noqa: ANN001
            return _Result()

    # resolve uses db.scalar(select...)
    got = await app_scope_mod.resolve_install_app_id(_Db(), tenant_id, agent_id=agent_id)
    assert got == app_id


@pytest.mark.asyncio
async def test_resolve_returns_none_without_ids():
    class _Db:
        async def scalar(self, _stmt):  # noqa: ANN001
            raise AssertionError("should not query")

    assert await app_scope_mod.resolve_install_app_id(_Db(), uuid4()) is None


@pytest.mark.asyncio
async def test_run_resource_before_wraps_app_then_agent():
    runner = HookRunner(SimpleNamespace(), uuid4())
    calls: list[tuple[HookScope, object]] = []

    async def fake_run(trigger, scope, target_id, payload):  # noqa: ANN001
        calls.append((scope, target_id))
        return HookRunResult(results=[{"scope": scope.value}], payload={**payload, "n": len(calls)})

    runner.run = fake_run  # type: ignore[method-assign]
    app_id = uuid4()
    agent_id = uuid4()
    out = await runner.run_resource(
        HookTrigger.BEFORE_CALL,
        HookScope.AGENT,
        agent_id,
        {"query": "q"},
        app_id=app_id,
        phase="before",
    )
    assert [c[0] for c in calls] == [HookScope.APP, HookScope.AGENT]
    assert calls[0][1] == app_id
    assert calls[1][1] == agent_id
    assert out.payload["n"] == 2
    assert len(out.results) == 2


@pytest.mark.asyncio
async def test_run_resource_after_wraps_agent_then_app():
    runner = HookRunner(SimpleNamespace(), uuid4())
    calls: list[HookScope] = []

    async def fake_run(trigger, scope, target_id, payload):  # noqa: ANN001
        calls.append(scope)
        return HookRunResult(results=[], payload=payload)

    runner.run = fake_run  # type: ignore[method-assign]
    await runner.run_resource(
        HookTrigger.AFTER_CALL,
        HookScope.FLOW,
        uuid4(),
        {},
        app_id=uuid4(),
        phase="after",
    )
    assert calls == [HookScope.FLOW, HookScope.APP]


@pytest.mark.asyncio
async def test_run_resource_without_app_only_resource():
    runner = HookRunner(SimpleNamespace(), uuid4())
    calls: list[HookScope] = []

    async def fake_run(trigger, scope, target_id, payload):  # noqa: ANN001
        calls.append(scope)
        return HookRunResult(results=[], payload=payload)

    runner.run = fake_run  # type: ignore[method-assign]
    await runner.run_resource(HookTrigger.BEFORE_CALL, HookScope.AGENT, uuid4(), {}, app_id=None)
    assert calls == [HookScope.AGENT]


def test_meta_app_scope_hint_not_reserved():
    from miles_portal.tenant.hooks.meta import hook_meta_dict

    scopes = {s.value: s for s in hook_meta_dict()["scopes"]}
    assert "app" in scopes
    assert "预留" not in (scopes["app"].hint or "")
