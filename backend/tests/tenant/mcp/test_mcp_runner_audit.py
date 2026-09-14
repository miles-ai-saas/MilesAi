"""``McpServiceManager`` 两处 Runner 调用的审计不变式特征化测试。

``_sync_stdio_service`` 与 ``invoke_tool``（STDIO 分支）各自复制了一份
「测时 → 成功写审计 / ``BadRequestError`` 写 error 审计并抛出」的序列。
本文件锁定该不变量与若干易被重构破坏的细节：

- 工具列表为空时，Runner 调用本身仍算成功 → 审计为 ``success``，
  业务失败只体现在 ``row.sync_error`` 上；
- ``_sync_stdio_service`` 的 error 路径除写审计外还会落 ``row`` 状态并 flush；
- ``invoke_tool`` 的非 STDIO 分支完全不走 Runner，也不写审计。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_exec.mcp.constants import McpTransport
from miles_portal.tenant.mcp.runner import audit as runner_audit_mod
from miles_portal.tenant.mcp.services import mcp as mcp_mod

TENANT_ID = uuid4()


class _Clock:
    """递增单调时钟：每对 (start, end) 差值恒为 250ms。"""

    def __init__(self, start: float = 20.0, step: float = 0.25) -> None:
        self._value = start
        self._step = step

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


class _FakeRunner:
    def __init__(self) -> None:
        self.list_calls: list[dict] = []
        self.call_calls: list[dict] = []
        self.list_error: Exception | None = None
        self.call_error: Exception | None = None
        self.tools: list[dict] = []
        self.output: dict = {"content": "ok"}

    async def list_tools(self, spec, connection_config):  # noqa: ANN001, ANN201
        self.list_calls.append({"spec": spec, "connection_config": connection_config})
        if self.list_error is not None:
            raise self.list_error
        return self.tools

    async def call_tool(self, spec, tool_name, arguments, connection_config):  # noqa: ANN001, ANN201
        self.call_calls.append(
            {
                "spec": spec,
                "tool_name": tool_name,
                "arguments": arguments,
                "connection_config": connection_config,
            }
        )
        if self.call_error is not None:
            raise self.call_error
        return self.output


class _FakeDb:
    def __init__(self, row=None) -> None:  # noqa: ANN001
        self._row = row
        self.flushes = 0

    async def get(self, _model, _pk):  # noqa: ANN001
        return self._row

    async def flush(self) -> None:
        self.flushes += 1


@pytest.fixture
def env(monkeypatch):
    audits: list[dict] = []
    runner = _FakeRunner()

    async def _write_audit(db, **kwargs):  # noqa: ANN001, ANN003
        audits.append({"db": db, **kwargs})

    monkeypatch.setattr(mcp_mod, "get_settings", lambda: SimpleNamespace(mcp_runner_enabled=True))
    monkeypatch.setattr(mcp_mod, "RunnerClient", lambda: runner)
    monkeypatch.setattr(mcp_mod, "write_mcp_runner_session", _write_audit)
    monkeypatch.setattr(mcp_mod, "build_run_spec", lambda row, ctx, purpose: SimpleNamespace(purpose=purpose))
    # 耗时由 record_runner_session 在审计模块内测量，故时钟打在那里
    monkeypatch.setattr(runner_audit_mod, "time", SimpleNamespace(monotonic=_Clock()))

    return SimpleNamespace(audits=audits, runner=runner)


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(tenant_id=TENANT_ID, user_id=uuid4(), is_superuser=True)


def _row(*, transport=McpTransport.STDIO.value, tools=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT_ID,
        name="demo-mcp",
        transport=transport,
        endpoint_url="https://mcp.example.com/mcp",
        connection_config={"command": "node"},
        tools_cache=tools if tools is not None else [{"name": "echo", "description": "回声"}],
        sync_error=None,
        status=None,
        last_sync_at=None,
    )


def _manager(db, row):  # noqa: ANN001
    mgr = mcp_mod.McpServiceManager(db, _ctx())
    mgr.db = db
    return mgr


# =========================================================================== #
# _sync_stdio_service
# =========================================================================== #


async def test_sync_disabled_sets_row_error_without_audit(env, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(mcp_mod, "get_settings", lambda: SimpleNamespace(mcp_runner_enabled=False))
    row = _row()
    db = _FakeDb()
    mgr = _manager(db, row)

    with pytest.raises(BadRequestError):
        await mgr._sync_stdio_service(row)

    assert env.audits == []
    assert row.sync_error is not None
    assert row.status == mcp_mod.McpStatus.ERROR
    assert db.flushes >= 1


async def test_sync_success_writes_single_success_audit(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb()
    env.runner.tools = [{"name": "echo"}]
    mgr = _manager(db, row)

    result = await mgr._sync_stdio_service(row)

    (audit,) = env.audits
    assert audit["status"] == "success"
    assert audit["duration_ms"] == 250
    assert audit["spec"].purpose == "mcp_sync"
    assert audit.get("error_message") is None
    assert result.tools == [{"name": "echo"}]
    assert row.status == mcp_mod.McpStatus.ACTIVE
    assert row.sync_error is None


async def test_sync_empty_tools_still_audits_success(env):  # noqa: ANN001
    """Runner 成功但工具为空：审计记 success，业务失败只落在 row 上。"""
    row = _row()
    db = _FakeDb()
    env.runner.tools = []
    mgr = _manager(db, row)

    result = await mgr._sync_stdio_service(row)

    (audit,) = env.audits
    assert audit["status"] == "success"
    assert row.status == mcp_mod.McpStatus.ERROR
    assert row.sync_error == "STDIO MCP 未返回工具列表"
    assert result.tools == row.tools_cache


async def test_sync_bad_request_writes_error_audit_then_reraises(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb()
    env.runner.list_error = BadRequestError("runner 不可达")
    mgr = _manager(db, row)

    with pytest.raises(BadRequestError):
        await mgr._sync_stdio_service(row)

    (audit,) = env.audits
    assert audit["status"] == "error"
    assert audit["error_message"] == "runner 不可达"
    # 审计之外还须落 row 状态并 flush
    assert row.sync_error == "runner 不可达"
    assert row.status == mcp_mod.McpStatus.ERROR
    assert db.flushes >= 1


async def test_sync_non_bad_request_writes_no_audit(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb()
    env.runner.list_error = RuntimeError("崩")
    mgr = _manager(db, row)

    with pytest.raises(RuntimeError):
        await mgr._sync_stdio_service(row)

    assert env.audits == []


# =========================================================================== #
# invoke_tool（STDIO 分支）
# =========================================================================== #


def _body(params=None) -> SimpleNamespace:  # noqa: ANN001
    return SimpleNamespace(params=params)


async def test_invoke_stdio_success_audit_carries_tool_name(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb(row)
    env.runner.output = {"content": "pong"}
    mgr = _manager(db, row)

    result = await mgr.invoke_tool(row.id, "echo", _body({"q": 1}))

    (audit,) = env.audits
    assert audit["status"] == "success"
    assert audit["duration_ms"] == 250
    assert audit["tool_name"] == "echo"
    assert audit["spec"].purpose == "mcp_invoke"
    assert result.output == {"content": "pong"}
    assert result.tool_name == "echo"


async def test_invoke_stdio_passes_params_and_connection_config(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb(row)
    mgr = _manager(db, row)

    await mgr.invoke_tool(row.id, "echo", _body({"q": 1}))

    (call,) = env.runner.call_calls
    assert call["tool_name"] == "echo"
    assert call["arguments"] == {"q": 1}
    assert call["connection_config"] == {"command": "node"}


async def test_invoke_stdio_bad_request_writes_error_audit_and_reraises(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb(row)
    env.runner.call_error = BadRequestError("工具执行失败")
    mgr = _manager(db, row)

    with pytest.raises(BadRequestError):
        await mgr.invoke_tool(row.id, "echo", _body())

    (audit,) = env.audits
    assert audit["status"] == "error"
    assert audit["error_message"] == "工具执行失败"
    assert audit["tool_name"] == "echo"


async def test_invoke_stdio_non_bad_request_writes_no_audit(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb(row)
    env.runner.call_error = RuntimeError("崩")
    mgr = _manager(db, row)

    with pytest.raises(RuntimeError):
        await mgr.invoke_tool(row.id, "echo", _body())

    assert env.audits == []


async def test_invoke_unknown_tool_rejected_without_audit(env):  # noqa: ANN001
    row = _row()
    db = _FakeDb(row)
    mgr = _manager(db, row)

    with pytest.raises(NotFoundError):
        await mgr.invoke_tool(row.id, "not-registered", _body())

    assert env.audits == []
    assert env.runner.call_calls == []


async def test_invoke_remote_transport_never_touches_runner(env, monkeypatch):  # noqa: ANN001
    """非 STDIO 走远程客户端，不经 Runner、不写审计。"""
    row = _row(transport=McpTransport.SSE.value)
    db = _FakeDb(row)
    mgr = _manager(db, row)
    remote_calls: list[tuple] = []

    async def _remote(endpoint_url, tool_name, params, *, transport, connection_config):  # noqa: ANN001
        remote_calls.append((tool_name, params))
        return {"content": "remote"}

    monkeypatch.setattr(mcp_mod, "remote_invoke_mcp_tool", _remote)

    result = await mgr.invoke_tool(row.id, "echo", _body({"q": 2}))

    assert remote_calls == [("echo", {"q": 2})]
    assert result.output == {"content": "remote"}
    assert env.audits == []
    assert env.runner.call_calls == []
