"""``skill_run_script`` 的审计不变式特征化测试。

与 ``invoke_custom_script`` 同构：每次 Runner 调用必须留下**恰好一条**
``McpRunnerSession`` 审计（成功 success / ``BadRequestError`` error + 原样抛出，
其他异常不记录）。差异点在于技能脚本 ``tool_id=None``、``tool_name`` 编码为
``skill:<slug>:<path>``。

该函数路径零覆盖（``test_skill_runtime_integration.py`` 只覆盖
``skill_read_reference``），故先锁定行为再消除重复调用序列。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_portal.tenant.mcp.runner import audit as runner_audit_mod
from miles_portal.tenant.mcp.runner import client as runner_client_mod
from miles_portal.tenant.skills import runtime as runtime_mod

TENANT_ID = uuid4()
ACTOR_ID = uuid4()
CTX_USER_ID = uuid4()
SKILL_ID = uuid4()
SOURCE = "print('skill')"


class _Clock:
    """递增单调时钟：每对 (start, end) 差值恒为 250ms。"""

    def __init__(self, start: float = 100.0, step: float = 0.25) -> None:
        self._value = start
        self._step = step

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.result: dict = {"stdout": "ok"}

    async def exec_script(self, **kwargs):  # noqa: ANN003, ANN201
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _skill() -> SimpleNamespace:
    return SimpleNamespace(id=SKILL_ID, slug="demo-skill", tenant_id=TENANT_ID, deleted_at=None, is_active=True)


@pytest.fixture
def env(monkeypatch):
    audits: list[dict] = []
    runner = _FakeRunner()

    async def _write_audit(db, **kwargs):  # noqa: ANN001, ANN003
        audits.append({"db": db, **kwargs})

    async def _resolve(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return _skill()

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: SimpleNamespace(mcp_runner_enabled=True))
    monkeypatch.setattr(runtime_mod, "resolve_bound_skill", _resolve)
    monkeypatch.setattr(runtime_mod, "read_skill_script_source", lambda *a, **k: SOURCE)  # noqa: ARG005
    monkeypatch.setattr(runtime_mod, "validate_script_source", lambda src: src.strip())
    # 耗时由 record_runner_session 在审计模块内测量，故时钟打在那里
    monkeypatch.setattr(runner_audit_mod, "time", SimpleNamespace(monotonic=_Clock()))
    # 函数内 import，须打源模块属性
    monkeypatch.setattr(runner_audit_mod, "write_script_runner_session", _write_audit)
    monkeypatch.setattr(runner_client_mod, "RunnerClient", lambda: runner)

    return SimpleNamespace(audits=audits, runner=runner)


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(tenant_id=TENANT_ID, user_id=CTX_USER_ID)


async def _run(*, env, params=None, actor_user_id=None, db=None):  # noqa: ANN001
    return await runtime_mod.skill_run_script(
        db if db is not None else object(),
        _ctx(),
        params if params is not None else {"path": "scripts/a.py"},
        actor_user_id=actor_user_id,
    )


# --------------------------------------------------------------------------- #
# 前置校验
# --------------------------------------------------------------------------- #


async def test_runner_disabled_audits_nothing(env, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(runtime_mod, "get_settings", lambda: SimpleNamespace(mcp_runner_enabled=False))

    with pytest.raises(BadRequestError):
        await _run(env=env)

    assert env.audits == []
    assert env.runner.calls == []


async def test_missing_path_audits_nothing(env):  # noqa: ANN001
    with pytest.raises(BadRequestError):
        await _run(env=env, params={"path": "   "})

    assert env.audits == []
    assert env.runner.calls == []


async def test_shell_script_rejected_before_runner(env):  # noqa: ANN001
    with pytest.raises(BadRequestError):
        await _run(env=env, params={"path": "scripts/a.sh"})

    assert env.audits == []
    assert env.runner.calls == []


async def test_missing_script_maps_to_not_found(env, monkeypatch):  # noqa: ANN001
    def _boom(*_a, **_k):
        raise FileNotFoundError

    monkeypatch.setattr(runtime_mod, "read_skill_script_source", _boom)

    with pytest.raises(NotFoundError):
        await _run(env=env)

    assert env.audits == []


# --------------------------------------------------------------------------- #
# 成功路径
# --------------------------------------------------------------------------- #


async def test_success_audit_uses_skill_tool_name_and_null_tool_id(env):  # noqa: ANN001
    env.runner.result = {"stdout": "done"}

    out = await _run(env=env)

    assert out == {"path": "scripts/a.py", "output": {"stdout": "done"}}
    (audit,) = env.audits
    assert audit["status"] == "success"
    assert audit["duration_ms"] == 250
    assert audit["tool_name"] == "skill:demo-skill:scripts/a.py"
    assert audit["tool_id"] is None  # 技能脚本不绑工具 ID
    assert audit["source"] == SOURCE
    assert audit["tenant_id"] == TENANT_ID
    assert audit.get("error_message") is None


async def test_actor_falls_back_to_ctx_user_id(env):  # noqa: ANN001
    await _run(env=env, actor_user_id=None)

    (call,) = env.runner.calls
    assert call["actor_user_id"] == CTX_USER_ID
    (audit,) = env.audits
    assert audit["actor_user_id"] == CTX_USER_ID


async def test_explicit_actor_overrides_ctx_user(env):  # noqa: ANN001
    await _run(env=env, actor_user_id=ACTOR_ID)

    (call,) = env.runner.calls
    assert call["actor_user_id"] == ACTOR_ID


async def test_script_params_exclude_control_keys(env):  # noqa: ANN001
    await _run(env=env, params={"path": "scripts/a.py", "skill_slug": "demo-skill", "x": 1, "y": "z"})

    (call,) = env.runner.calls
    assert call["params"] == {"x": 1, "y": "z"}


async def test_nested_params_dict_takes_precedence(env):  # noqa: ANN001
    await _run(env=env, params={"path": "scripts/a.py", "params": {"n": 5}})

    (call,) = env.runner.calls
    assert call["params"] == {"n": 5}


# --------------------------------------------------------------------------- #
# 失败路径
# --------------------------------------------------------------------------- #


async def test_bad_request_writes_error_audit_and_reraises(env):  # noqa: ANN001
    env.runner.error = BadRequestError("脚本超时")

    with pytest.raises(BadRequestError):
        await _run(env=env)

    (audit,) = env.audits
    assert audit["status"] == "error"
    assert audit["error_message"] == "脚本超时"
    assert audit["tool_name"] == "skill:demo-skill:scripts/a.py"


async def test_non_bad_request_exception_writes_no_audit(env):  # noqa: ANN001
    env.runner.error = RuntimeError("runner 挂")

    with pytest.raises(RuntimeError):
        await _run(env=env)

    assert env.audits == []
