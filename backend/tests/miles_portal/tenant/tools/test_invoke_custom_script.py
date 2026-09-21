"""``invoke_custom_script`` 的审计不变式特征化测试。

每次 Runner 脚本调用必须留下**恰好一条** ``McpRunnerSession`` 审计：
成功记 ``status="success"``，``BadRequestError`` 记 ``status="error"`` 并附
``error_message``；其他异常完全不写审计（原样冒泡）。

该不变量此前只靠 4 处复制粘贴的 try/except 保证（另 3 处在
``skills/runtime.py`` 与 ``mcp/services/mcp.py``），且这些路径零测试覆盖。
本文件先锁定行为，作为消除重复调用序列的安全网。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.mcp.runner import audit as runner_audit_mod
from miles_portal.tenant.tools.invoke import custom as custom_mod

TENANT_ID = uuid4()
ACTOR_ID = uuid4()
TOOL_ID = uuid4()
SOURCE = "print('hi')"


class _Clock:
    """递增单调时钟：每次调用前进 ``step``，使每对 (start, end) 差值恒为 250ms。"""

    def __init__(self, start: float = 10.0, step: float = 0.25) -> None:
        self._value = start
        self._step = step

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


class _FakeRunner:
    """``RunnerClient`` 替身：记录 exec_script 入参，可注入异常。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.result: dict = {"stdout": "ok"}

    async def exec_script(self, **kwargs):  # noqa: ANN003, ANN201
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _tool(config: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=TOOL_ID, slug="my-script", parameters=[], config=config or {"source": SOURCE})


@pytest.fixture
def env(monkeypatch):
    """装配替身：审计收集器 + Runner 假客户端 + 递增时钟（每对调用 250ms）。"""
    audits: list[dict] = []
    runner = _FakeRunner()

    async def _write_audit(db, **kwargs):  # noqa: ANN001, ANN003
        audits.append({"db": db, **kwargs})

    monkeypatch.setattr(custom_mod, "write_script_runner_session", _write_audit)
    monkeypatch.setattr(custom_mod, "RunnerClient", lambda: runner)
    monkeypatch.setattr(custom_mod, "validate_tool_params", lambda spec, params: dict(params))
    monkeypatch.setattr(custom_mod, "validate_script_source", lambda src: src.strip())
    monkeypatch.setattr(custom_mod, "get_settings", lambda: SimpleNamespace(mcp_runner_enabled=True))
    # 耗时由 record_runner_session 在审计模块内测量，故时钟打在那里
    monkeypatch.setattr(runner_audit_mod, "time", SimpleNamespace(monotonic=_Clock()))

    return SimpleNamespace(audits=audits, runner=runner)


async def _invoke(*, env, tool=None, params=None, db=None):  # noqa: ANN001
    ctx = SimpleNamespace(tenant_id=TENANT_ID, user_id=ACTOR_ID)
    return await custom_mod.invoke_custom_script(
        db if db is not None else object(),
        tool or _tool(),
        params if params is not None else {},
        ctx=ctx,
        actor_user_id=ACTOR_ID,
    )


# --------------------------------------------------------------------------- #
# 前置校验：不触达 Runner，也不写审计
# --------------------------------------------------------------------------- #


async def test_runner_disabled_audits_nothing(env, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(custom_mod, "get_settings", lambda: SimpleNamespace(mcp_runner_enabled=False))

    with pytest.raises(BadRequestError):
        await _invoke(env=env)

    assert env.audits == []
    assert env.runner.calls == []


# --------------------------------------------------------------------------- #
# 成功路径
# --------------------------------------------------------------------------- #


async def test_success_writes_single_audit_with_elapsed_and_tool_identity(env):  # noqa: ANN001
    env.runner.result = {"stdout": "hello"}

    out = await _invoke(env=env)

    assert out == {"stdout": "hello"}
    (audit,) = env.audits
    assert audit["status"] == "success"
    assert audit["duration_ms"] == 250
    assert audit.get("error_message") is None  # 成功路径省略该参数（下游默认 None）
    assert audit["tool_name"] == "my-script"
    assert audit["source"] == SOURCE
    assert audit["tenant_id"] == TENANT_ID
    # 审计表无 tool_id 列；工具 UUID 由 tool_invocation_logs 记录，此处不传
    assert "tool_id" not in audit


async def test_success_audit_uses_caller_db(env):  # noqa: ANN001
    """审计写入使用调用方传入的 db（不自开会话）。"""
    db = object()

    await _invoke(env=env, db=db)

    (audit,) = env.audits
    assert audit["db"] is db


async def test_exec_receives_validated_params_and_clamped_limits(env):  # noqa: ANN001
    tool = _tool({"source": SOURCE, "timeout_sec": 9999, "max_memory_mb": 1})

    await _invoke(env=env, tool=tool, params={"a": 1})

    (call,) = env.runner.calls
    assert call["params"] == {"a": 1}
    assert call["max_runtime_sec"] == 120  # 上夹取
    assert call["max_memory_mb"] == 128  # 下夹取
    assert call["tool_id"] == TOOL_ID
    assert call["actor_user_id"] == ACTOR_ID
    assert call["tenant_id"] == TENANT_ID


# --------------------------------------------------------------------------- #
# 失败路径
# --------------------------------------------------------------------------- #


async def test_bad_request_writes_error_audit_and_reraises(env):  # noqa: ANN001
    env.runner.error = BadRequestError("沙箱超时")

    with pytest.raises(BadRequestError):
        await _invoke(env=env)

    (audit,) = env.audits
    assert audit["status"] == "error"
    assert audit["duration_ms"] == 250
    assert audit["error_message"] == "沙箱超时"
    assert audit["tool_name"] == "my-script"


async def test_non_bad_request_exception_writes_no_audit(env):  # noqa: ANN001
    """只有 BadRequestError 才记审计；其他异常原样冒泡、不留记录。"""
    env.runner.error = RuntimeError("runner 崩了")

    with pytest.raises(RuntimeError):
        await _invoke(env=env)

    assert env.audits == []


async def test_exactly_one_audit_row_per_call(env):  # noqa: ANN001
    """成功与失败路径都只写一条，不重复。"""
    await _invoke(env=env)
    env.runner.error = BadRequestError("失败")
    with pytest.raises(BadRequestError):
        await _invoke(env=env)

    assert [a["status"] for a in env.audits] == ["success", "error"]
