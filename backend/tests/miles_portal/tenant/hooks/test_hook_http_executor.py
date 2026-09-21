"""``HookHttpMixin._run_http`` 的特征化测试。

补齐既有测试未覆盖的分支：缺 url、HTTP 非 2xx、``block`` 动作、传输异常、
``on_failure=fail_request`` 的前后置差异，以及每次路径写入的审计日志字段。
用于在重构（消除 5 处重复 ``_write_log`` 调用）前锁定行为。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_portal.tenant.hooks.exceptions import HookBlockedError
from miles_portal.tenant.hooks.models import HookScope, HookTrigger, HookType
from miles_portal.tenant.hooks.services.executor import http as http_mod
from miles_portal.tenant.hooks.services.executor.service import HookExecutor

HOOK_NAME = "h"


# --- 替身 -------------------------------------------------------------------


def _db():
    """记录被 ``add`` 的审计日志行。"""
    rows: list = []
    return SimpleNamespace(add=rows.append, rows=rows)


def _hook(*, config=None, name=HOOK_NAME):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        hook_type=HookType.HTTP,
        config={"url": "https://example.com/hook"} if config is None else config,
    )


def _binding(hook):
    return SimpleNamespace(id=uuid4(), hook=hook)


class _Resp:
    def __init__(self, *, status_code: int = 200, body: bytes = b'{"action": "continue"}') -> None:
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self.content = body
        self.text = body.decode("utf-8")

    def json(self):
        return json.loads(self.content)


def _client_factory(resp=None, *, exc: BaseException | None = None):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):  # noqa: ARG002
            return False

        async def request(self, *args, **kwargs):  # noqa: ARG002
            if exc is not None:
                raise exc
            return resp

    return lambda **kw: _Client()  # noqa: ARG005


async def _run(*, hook, db, monkeypatch, resp=None, exc=None, trigger=HookTrigger.BEFORE_CALL, payload=None):
    if resp is not None or exc is not None:
        monkeypatch.setattr(http_mod.httpx, "AsyncClient", _client_factory(resp, exc=exc))
    ex = HookExecutor(db, uuid4())
    return await ex._run_http(
        hook,
        binding=_binding(hook),
        trigger=trigger,
        scope=HookScope.GLOBAL,
        target_id=None,
        payload=payload if payload is not None else {"query": "原始"},
        trace_id=None,
    )


# --- 缺 url -----------------------------------------------------------------


async def test_missing_url_returns_error_without_http_call(monkeypatch):
    db = _db()
    item, payload = await _run(hook=_hook(config={}), db=db, monkeypatch=monkeypatch)
    assert item == {"hook": HOOK_NAME, "status": "error", "reason": "missing url"}
    assert payload == {"query": "原始"}
    assert len(db.rows) == 1
    assert db.rows[0].status == "error"
    assert db.rows[0].error_message == "missing url"
    assert db.rows[0].duration_ms == 0


# --- HTTP 非 2xx -------------------------------------------------------------


async def test_http_error_returns_error_item_and_keeps_payload(monkeypatch):
    db = _db()
    item, payload = await _run(hook=_hook(), db=db, monkeypatch=monkeypatch, resp=_Resp(status_code=500, body=b"boom"))
    assert item == {"hook": HOOK_NAME, "status": "error", "http_status": 500}
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "error"
    assert db.rows[0].http_status == 500
    assert db.rows[0].error_message == "http_500"


async def test_http_error_includes_body_when_requested(monkeypatch):
    db = _db()
    hook = _hook()
    monkeypatch.setattr(http_mod.httpx, "AsyncClient", _client_factory(_Resp(status_code=400, body=b"bad")))
    ex = HookExecutor(db, uuid4())
    item, _ = await ex._run_http(
        hook,
        binding=_binding(hook),
        trigger=HookTrigger.BEFORE_CALL,
        scope=HookScope.GLOBAL,
        target_id=None,
        payload={},
        trace_id=None,
        include_body=True,
    )
    assert item["body"] == "bad"


async def test_http_error_fail_request_raises_only_for_before_triggers(monkeypatch):
    config = {"url": "https://example.com/hook", "on_failure": "fail_request"}
    db = _db()
    with pytest.raises(HookBlockedError, match="调用失败"):
        await _run(hook=_hook(config=config), db=db, monkeypatch=monkeypatch, resp=_Resp(status_code=503))
    # 抛错前仍写了审计日志
    assert db.rows[0].status == "error"


async def test_http_error_fail_request_does_not_raise_for_after_trigger(monkeypatch):
    config = {"url": "https://example.com/hook", "on_failure": "fail_request"}
    db = _db()
    item, _ = await _run(
        hook=_hook(config=config),
        db=db,
        monkeypatch=monkeypatch,
        resp=_Resp(status_code=503),
        trigger=HookTrigger.AFTER_CALL,
    )
    assert item["status"] == "error"


# --- block 动作 -------------------------------------------------------------


async def test_block_action_blocks_before_trigger(monkeypatch):
    db = _db()
    item, payload = await _run(
        hook=_hook(),
        db=db,
        monkeypatch=monkeypatch,
        resp=_Resp(body=b'{"action": "block", "message": "\xe4\xb8\x8d\xe5\x85\x81\xe8\xae\xb8"}'),
    )
    assert item == {"hook": HOOK_NAME, "status": "blocked", "message": "不允许"}
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "blocked"
    assert db.rows[0].response_action == "block"
    assert db.rows[0].error_message == "不允许"


async def test_block_action_is_not_blocking_for_after_trigger(monkeypatch):
    """AFTER_* 阶段无 payload 可阻断，故降级为 ok 并保留 action 供调用方观察。"""
    db = _db()
    item, payload = await _run(
        hook=_hook(),
        db=db,
        monkeypatch=monkeypatch,
        resp=_Resp(body=b'{"action": "block", "message": "x"}'),
        trigger=HookTrigger.AFTER_CALL,
    )
    assert item["status"] == "ok"
    assert item["action"] == "block"
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "ok"


# --- modify 动作 ------------------------------------------------------------


async def test_modify_action_merges_allowlisted_fields(monkeypatch):
    db = _db()
    item, payload = await _run(
        hook=_hook(),
        db=db,
        monkeypatch=monkeypatch,
        resp=_Resp(body=b'{"action": "modify", "modify": {"query": "\xe6\x94\xb9\xe5\x86\x99", "forbidden": "x"}}'),
    )
    assert item["action"] == "modify"
    assert payload == {"query": "改写"}  # 非白名单键被丢弃


# --- 非 JSON 响应体 ---------------------------------------------------------


async def test_non_json_response_falls_back_to_continue(monkeypatch):
    db = _db()
    item, payload = await _run(hook=_hook(), db=db, monkeypatch=monkeypatch, resp=_Resp(body=b"not json"))
    assert item["status"] == "ok"
    assert item["action"] == "continue"
    assert payload == {"query": "原始"}


# --- 传输异常 ---------------------------------------------------------------


async def test_transport_exception_returns_error_item(monkeypatch):
    db = _db()
    item, payload = await _run(hook=_hook(), db=db, monkeypatch=monkeypatch, exc=RuntimeError("connection refused"))
    assert item["status"] == "error"
    assert "connection refused" in item["reason"]
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "error"


async def test_transport_exception_fail_request_raises_before_trigger(monkeypatch):
    config = {"url": "https://example.com/hook", "on_failure": "fail_request"}
    db = _db()
    with pytest.raises(HookBlockedError, match="调用异常") as ei:
        await _run(hook=_hook(config=config), db=db, monkeypatch=monkeypatch, exc=RuntimeError("boom"))
    assert isinstance(ei.value.__cause__, RuntimeError)  # 保留异常链便于定位根因
    assert db.rows[0].status == "error"


async def test_transport_exception_truncates_reason(monkeypatch):
    db = _db()
    item, _ = await _run(hook=_hook(), db=db, monkeypatch=monkeypatch, exc=RuntimeError("x" * 900))
    assert len(item["reason"]) == 500


# --- 成功路径的审计日志 ------------------------------------------------------


async def test_success_writes_ok_log_with_duration(monkeypatch):
    db = _db()
    item, _ = await _run(hook=_hook(), db=db, monkeypatch=monkeypatch, resp=_Resp(status_code=200))
    assert item["status"] == "ok"
    assert db.rows[0].status == "ok"
    assert db.rows[0].http_status == 200
    assert db.rows[0].response_action == "continue"
    assert db.rows[0].error_message is None
    assert db.rows[0].duration_ms >= 0


async def test_custom_method_and_headers_are_passed_through(monkeypatch):
    captured: dict = {}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):  # noqa: ARG002
            return False

        async def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return _Resp()

    monkeypatch.setattr(http_mod.httpx, "AsyncClient", lambda **kw: _Client())  # noqa: ARG005
    db = _db()
    hook = _hook(config={"url": "https://example.com/hook", "method": "put", "headers": {"X-K": "v"}, "timeout": 3})
    await _run(hook=hook, db=db, monkeypatch=monkeypatch)
    assert captured["method"] == "PUT"
    assert captured["url"] == "https://example.com/hook"
    assert captured["headers"] == {"X-K": "v"}
    assert captured["json"]["schema_version"]
