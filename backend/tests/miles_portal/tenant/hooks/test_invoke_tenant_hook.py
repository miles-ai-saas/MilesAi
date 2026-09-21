"""invoke_tenant_hook：仅 HTTP、blocked 不抛、参数枚举校验、include_body 契约。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.hooks.exceptions import HookBlockedError
from miles_portal.tenant.hooks.models import HookScope, HookTrigger, HookType
from miles_portal.tenant.hooks.services.executor import http as http_mod
from miles_portal.tenant.hooks.services.executor.service import HookExecutor
from miles_portal.tenant.tools.services import hook_once


def _ctx(tenant_id=None) -> SimpleNamespace:
    return SimpleNamespace(tenant_id=tenant_id or uuid4(), is_superuser=False, permissions=frozenset())


def _binding(hook):
    return SimpleNamespace(id=uuid4(), hook=hook)


def _db():
    """最小假会话：仅需 ``add`` 以容纳 HookExecutionLog。"""
    return SimpleNamespace(add=lambda row: None)


def _hook(hook_type=HookType.HTTP, name="h"):
    return SimpleNamespace(id=uuid4(), name=name, hook_type=hook_type, config={"url": "https://example.com/hook"})


class _Exec:
    """记录 run_manual_http 调用的假执行器。"""

    calls: dict = {}

    def __init__(self, db, tenant_id) -> None:
        pass

    async def run_manual_http(self, *, trigger, scope, target_id, payload):
        _Exec.calls = {"trigger": trigger, "scope": scope, "target_id": target_id, "payload": payload}
        return [{"hook": "h", "status": "ok"}], {**payload, "extra": 1}


# --- 服务层：参数解析与委托 ---


async def test_service_parses_enums_and_delegates(monkeypatch):
    monkeypatch.setattr(hook_once, "HookExecutor", _Exec)
    out = await hook_once.run_registered_http_hooks(
        object(),
        _ctx(),
        trigger="before_call",
        scope="agent",
        target_id=str(uuid4()),
        payload={"query": "hi"},
    )
    assert _Exec.calls["trigger"] is HookTrigger.BEFORE_CALL
    assert _Exec.calls["scope"] is HookScope.AGENT
    assert _Exec.calls["payload"] == {"query": "hi"}
    assert out["trigger"] == "before_call"
    assert out["scope"] == "agent"
    assert out["count"] == 1
    assert out["payload"] == {"query": "hi", "extra": 1}


async def test_service_defaults_scope_to_global(monkeypatch):
    monkeypatch.setattr(hook_once, "HookExecutor", _Exec)
    out = await hook_once.run_registered_http_hooks(object(), _ctx(), trigger="after_call")
    assert _Exec.calls["scope"] is HookScope.GLOBAL
    assert out["scope"] == "global"


async def test_service_rejects_invalid_trigger():
    with pytest.raises(BadRequestError, match="trigger"):
        await hook_once.run_registered_http_hooks(object(), _ctx(), trigger="nope")


async def test_service_rejects_missing_trigger():
    with pytest.raises(BadRequestError, match="trigger"):
        await hook_once.run_registered_http_hooks(object(), _ctx(), trigger=None)


async def test_service_rejects_invalid_target_id():
    with pytest.raises(BadRequestError, match="target_id"):
        await hook_once.run_registered_http_hooks(object(), _ctx(), trigger="before_call", target_id="not-a-uuid")


async def test_service_reports_when_no_hook_matched(monkeypatch):
    class _Empty(_Exec):
        async def run_manual_http(self, *, trigger, scope, target_id, payload):
            return [], payload

    monkeypatch.setattr(hook_once, "HookExecutor", _Empty)
    out = await hook_once.run_registered_http_hooks(object(), _ctx(), trigger="before_call")
    assert out["count"] == 0
    assert "未找到" in out["message"]


# --- 执行器：仅 HTTP、blocked 不抛 ---


async def test_manual_http_skips_python_hooks(monkeypatch):
    http_hook, py_hook = _hook(name="h1"), _hook(hook_type=HookType.PYTHON, name="h2")
    ex = HookExecutor(_db(), uuid4())
    monkeypatch.setattr(
        ex,
        "_load_bindings",
        _async_ret([(_binding(http_hook), http_hook), (_binding(py_hook), py_hook)]),
    )
    seen: list[str] = []

    async def fake_run_http(hook, **kwargs):
        seen.append(hook.name)
        assert kwargs["include_body"] is True
        return {"hook": hook.name, "status": "ok"}, kwargs["payload"]

    monkeypatch.setattr(ex, "_run_http", fake_run_http)
    results, _ = await ex.run_manual_http(trigger=HookTrigger.BEFORE_CALL, scope=HookScope.GLOBAL, target_id=None, payload={})
    assert seen == ["h1"]
    assert [r["hook"] for r in results] == ["h1"]


async def test_manual_http_does_not_raise_on_block(monkeypatch):
    hook = _hook()
    ex = HookExecutor(_db(), uuid4())
    monkeypatch.setattr(ex, "_load_bindings", _async_ret([(_binding(hook), hook)]))

    async def fake_run_http(hook, **kwargs):  # noqa: ARG001
        raise HookBlockedError("被拦截", hook_name="h")

    monkeypatch.setattr(ex, "_run_http", fake_run_http)
    results, payload = await ex.run_manual_http(trigger=HookTrigger.BEFORE_CALL, scope=HookScope.GLOBAL, target_id=None, payload={"query": "q"})
    assert results == [{"hook": "h", "status": "blocked", "message": "被拦截"}]
    assert payload == {"query": "q"}


# --- _run_http：include_body 仅在显式开启时返回响应体 ---


class _Resp:
    status_code = 200
    is_success = True
    text = '{"action": "modify", "modify": {"query": "改写"}}'
    content = text.encode("utf-8")

    def json(self):
        return json.loads(self.content)


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):  # noqa: ARG002
        return False

    async def request(self, *args, **kwargs):  # noqa: ARG002
        return _Resp()


async def test_run_http_includes_body_when_requested(monkeypatch):
    monkeypatch.setattr(http_mod.httpx, "AsyncClient", lambda **kw: _Client())  # noqa: ARG005
    hook = _hook()
    ex = HookExecutor(_db(), uuid4())
    item, payload = await ex._run_http(
        hook,
        binding=_binding(hook),
        trigger=HookTrigger.BEFORE_CALL,
        scope=HookScope.GLOBAL,
        target_id=None,
        payload={"query": "原始"},
        trace_id=None,
        include_body=True,
    )
    assert item["body"] == _Resp.text
    assert item["action"] == "modify"
    assert payload["query"] == "改写"


async def test_run_http_omits_body_by_default(monkeypatch):
    monkeypatch.setattr(http_mod.httpx, "AsyncClient", lambda **kw: _Client())  # noqa: ARG005
    hook = _hook()
    ex = HookExecutor(_db(), uuid4())
    item, _ = await ex._run_http(
        hook,
        binding=_binding(hook),
        trigger=HookTrigger.BEFORE_CALL,
        scope=HookScope.GLOBAL,
        target_id=None,
        payload={},
        trace_id=None,
    )
    assert "body" not in item


def _async_ret(value):
    async def _inner(*args, **kwargs):  # noqa: ARG001
        return value

    return _inner
