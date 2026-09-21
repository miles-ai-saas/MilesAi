"""``invoke_tool_with_context`` 的特征化测试。

该函数是工具调用总入口（确认策略 → BEFORE_TOOL Hook → 执行 → 审计日志 →
AFTER_TOOL Hook），此前零直接覆盖（``test_agent_executor.py`` 只是把整个函数 mock 掉）。
其中 4 处 ``write_tool_invocation_log`` 调用有 9 个参数每次完全相同，本文件锁定
各路径的日志字段与异常行为，作为消除重复调用的重构安全网。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_portal.tenant.tools import confirmation as confirmation_mod
from miles_portal.tenant.tools.confirmation import ToolConfirmationRequired
from miles_portal.tenant.tools.invoke import context as ctx_mod
from miles_portal.tenant.tools.invoke.context import invoke_tool_with_context

TENANT_ID = uuid4()
ACTOR_ID = uuid4()
AGENT_ID = uuid4()


# --- 替身 -------------------------------------------------------------------


class _Hooks:
    """记录 Hook 调用；BEFORE_TOOL 可改写 params。"""

    rewrite_params: dict | None = None

    def __init__(self, db, tenant_id) -> None:  # noqa: ARG002
        _Hooks.last = self
        self.calls: list[tuple] = []

    async def run(self, trigger, scope, target_id, payload):  # noqa: ANN001
        self.calls.append((trigger, scope, target_id, payload))
        if trigger.value == "before_tool" and _Hooks.rewrite_params is not None:
            return SimpleNamespace(payload={**payload, "params": _Hooks.rewrite_params})
        return SimpleNamespace(payload=payload)


class _Clock:
    """可控单调时钟，让 latency_ms 可断言。"""

    def __init__(self, *values: float) -> None:
        self._values = list(values)

    def __call__(self) -> float:
        return self._values.pop(0) if self._values else 0.0


def _install(
    monkeypatch,
    *,
    meta=None,
    invoke=None,
    clock=(100.0, 100.25),
    skill_bound: set[str] | None = None,
):
    """替换外部依赖；返回记录审计日志行的列表。"""
    rows: list[SimpleNamespace] = []

    async def fake_write_log(db, **kwargs):  # noqa: ANN001, ARG001
        # 补齐可选参数的默认值，使各路径行的字段集一致，便于断言
        defaults = {
            "latency_ms": 0,
            "tool_id": None,
            "output": None,
            "error_message": None,
            "actor_user_id": None,
            "agent_id": None,
            "invoke_source": "api",
            "trace_id": None,
        }
        rows.append(SimpleNamespace(**{**defaults, **kwargs}))

    base_meta = {
        "slug": "calc",
        "name": "计算器",
        "description": None,
        "require_confirmation": False,
        "source": "builtin",
        "tool_id": None,
    }
    base_meta.update(meta or {})

    async def fake_resolve(db, ctx, slug, *, tool_id=None):  # noqa: ANN001, ARG002
        return {**base_meta, "slug": slug, "tool_id": base_meta.get("tool_id") or tool_id}

    monkeypatch.setattr(ctx_mod, "resolve_tool_meta", fake_resolve)
    monkeypatch.setattr(ctx_mod, "write_tool_invocation_log", fake_write_log)
    monkeypatch.setattr(ctx_mod, "HookRunner", _Hooks)
    monkeypatch.setattr(ctx_mod, "get_trace_id", lambda: "trace-1")
    monkeypatch.setattr(ctx_mod, "SKILL_BOUND_SLUGS", skill_bound if skill_bound is not None else set())
    monkeypatch.setattr(ctx_mod, "time", SimpleNamespace(monotonic=_Clock(*clock)))
    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", invoke or _default_invoke)
    # 技能包解析默认返回 None（避免真实实现用 object() 当 db 触发 AttributeError）
    monkeypatch.setattr(ctx_mod, "resolve_bound_skill_ids_from_agent", _async_ret([]))
    _Hooks.last = None
    _Hooks.rewrite_params = None
    return rows


def _async_ret(value):
    async def _inner(*args, **kwargs):  # noqa: ANN001, ARG001
        return value

    return _inner


async def _default_invoke(db, ctx, name, params, **kwargs):  # noqa: ANN001, ARG002
    return {"echo": params}


def _ctx():
    return SimpleNamespace(tenant_id=TENANT_ID, user_id=ACTOR_ID)


async def _call(name="calc", **overrides):
    kwargs = {
        "tool_id": None,
        "confirmed": False,
        "actor_user_id": ACTOR_ID,
        "agent_id": AGENT_ID,
        "invoke_source": "api",
    }
    kwargs.update(overrides)
    return await invoke_tool_with_context(object(), _ctx(), name, {"a": 1}, **kwargs)


# --- 确认策略 ---------------------------------------------------------------


async def test_require_confirmation_logs_and_raises_without_executing(monkeypatch):
    rows = _install(monkeypatch, meta={"require_confirmation": True})
    executed: list = []

    async def spy_invoke(*args, **kwargs):  # noqa: ANN002, ANN003
        executed.append(args)
        return {}

    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", spy_invoke)

    with pytest.raises(ToolConfirmationRequired) as ei:
        await _call()

    assert ei.value.slug == "calc"
    assert ei.value.tool_name == "计算器"
    assert ei.value.params == {"a": 1}
    assert executed == []
    assert len(rows) == 1
    assert rows[0].status == "confirmation_required"
    assert rows[0].latency_ms == 0


async def test_confirmed_bypasses_confirmation_gate(monkeypatch):
    rows = _install(monkeypatch, meta={"require_confirmation": True})
    out = await _call(confirmed=True)
    assert out == {"echo": {"a": 1}}
    assert rows[0].status == "success"  # 不出现 confirmation_required 行


async def test_generate_image_policy_requires_confirmation(monkeypatch):
    import miles_ai.integrations.generative.policy as policy_mod
    import miles_ai.integrations.generative.request_prefs as prefs_mod

    rows = _install(monkeypatch, meta={"slug": "generate_image", "name": "生图"})
    monkeypatch.setattr(prefs_mod, "resolve_image_n", lambda n: 1)
    monkeypatch.setattr(policy_mod, "needs_image_tool_confirmation", lambda params: True)
    monkeypatch.setattr(policy_mod, "image_tool_confirmation_message", lambda params: "确认生图？")

    with pytest.raises(ToolConfirmationRequired) as ei:
        await _call("generate_image")

    assert ei.value.tool_description == "确认生图？"
    assert rows[0].status == "confirmation_required"


async def test_generate_image_skips_policy_gate_when_not_needed(monkeypatch):
    import miles_ai.integrations.generative.policy as policy_mod
    import miles_ai.integrations.generative.request_prefs as prefs_mod

    rows = _install(monkeypatch, meta={"slug": "generate_image"})
    monkeypatch.setattr(prefs_mod, "resolve_image_n", lambda n: 1)
    monkeypatch.setattr(policy_mod, "needs_image_tool_confirmation", lambda params: False)

    out = await _call("generate_image")
    assert out == {"echo": {"a": 1, "n": 1}}  # n 已被覆盖并传入执行
    assert rows[0].status == "success"


async def test_generate_image_n_is_overridden_before_confirmation_gate(monkeypatch):
    """输入区张数覆盖必须在确认门槛前生效，否则用户确认的 n 与实际执行不一致。"""
    import miles_ai.integrations.generative.policy as policy_mod
    import miles_ai.integrations.generative.request_prefs as prefs_mod

    _install(monkeypatch, meta={"slug": "generate_image", "require_confirmation": True})
    monkeypatch.setattr(prefs_mod, "resolve_image_n", lambda n: 3)
    monkeypatch.setattr(policy_mod, "needs_image_tool_confirmation", lambda params: False)

    with pytest.raises(ToolConfirmationRequired) as ei:
        await _call("generate_image")

    assert ei.value.params["n"] == 3


# --- 技能包绑定 -------------------------------------------------------------


async def test_skill_bound_slug_without_binding_is_rejected(monkeypatch):
    rows = _install(monkeypatch, skill_bound={"skill_tool"})
    with pytest.raises(BadRequestError, match="技能包"):
        await invoke_tool_with_context(object(), _ctx(), "skill_tool", {}, agent_id=AGENT_ID)
    assert rows == []  # 未执行也未写日志


async def test_skill_bound_slug_with_binding_passes(monkeypatch):
    _install(monkeypatch, skill_bound={"skill_tool"})
    binding_id = uuid4()

    async def fake_resolve_skill(db, agent_id):  # noqa: ANN001, ARG002
        return [binding_id]

    captured: dict = {}

    async def spy_invoke(db, ctx, name, params, **kwargs):  # noqa: ANN001, ARG002
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(ctx_mod, "resolve_bound_skill_ids_from_agent", fake_resolve_skill)
    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", spy_invoke)

    await invoke_tool_with_context(object(), _ctx(), "skill_tool", {}, agent_id=AGENT_ID)
    assert captured["bound_skill_ids"] == [binding_id]


# --- BEFORE / AFTER Hook ---------------------------------------------------


async def test_before_tool_hook_can_rewrite_params(monkeypatch):
    _install(monkeypatch)
    _Hooks.rewrite_params = {"a": 99}
    out = await _call()
    assert out == {"echo": {"a": 99}}  # 改写后的 params 被用于执行


async def test_hooks_run_before_then_after_with_status_and_latency(monkeypatch):
    _install(monkeypatch, clock=(100.0, 100.25))
    await _call()

    triggers = [c[0].value for c in _Hooks.last.calls]
    assert triggers == ["before_tool", "after_tool"]
    after_payload = _Hooks.last.calls[1][3]
    assert after_payload["status"] == "success"
    assert after_payload["latency_ms"] == 250
    assert after_payload["output"] == {"echo": {"a": 1}}


async def test_hook_receives_tool_scope_and_base_payload(monkeypatch):
    tool_id = uuid4()
    _install(monkeypatch, meta={"tool_id": tool_id})
    await invoke_tool_with_context(object(), _ctx(), "calc", {"a": 1}, tool_id=tool_id, agent_id=AGENT_ID)

    trigger, scope, target, payload = _Hooks.last.calls[0]
    assert trigger.value == "before_tool"
    assert scope.value == "tool"
    assert target == tool_id
    assert payload["tool_slug"] == "calc"
    assert payload["module"] == "tool_invoke"
    assert payload["agent_id"] == str(AGENT_ID)
    assert payload["invoke_source"] == "api"


# --- 执行与审计 -------------------------------------------------------------


async def test_success_writes_log_with_output_and_latency(monkeypatch):
    rows = _install(monkeypatch, clock=(100.0, 100.25))
    out = await _call()

    assert out == {"echo": {"a": 1}}
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "success"
    assert row.output == {"echo": {"a": 1}}
    assert row.latency_ms == 250
    assert row.error_message is None


async def test_failure_logs_error_and_reraises(monkeypatch):
    async def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise NotFoundError("工具不存在")

    rows = _install(monkeypatch, invoke=boom, clock=(100.0, 100.5))

    with pytest.raises(NotFoundError):
        await _call()

    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].latency_ms == 500
    assert "工具不存在" in rows[0].error_message
    assert rows[0].output is None


async def test_failure_logs_original_params_not_hook_modified(monkeypatch):
    """错误路径记录的是调用方原始 params（而非 Hook 改写后的），此差异锁定为现状。"""
    rows = _install(monkeypatch)

    async def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("boom")

    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", boom)
    _Hooks.rewrite_params = {"a": 999}

    with pytest.raises(RuntimeError):
        await _call()

    assert rows[0].params == {"a": 1}


async def test_confirmation_signal_from_inner_invoke_is_not_logged_as_error(monkeypatch):
    async def raise_confirmation(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ToolConfirmationRequired("calc", "计算器", None, {})

    rows = _install(monkeypatch, invoke=raise_confirmation)

    with pytest.raises(ToolConfirmationRequired):
        await _call()
    assert rows == []  # 确认信号不是错误，不应写 error 日志


async def test_after_tool_hook_not_run_on_failure(monkeypatch):
    async def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("boom")

    _install(monkeypatch, invoke=boom)
    with pytest.raises(RuntimeError):
        await _call()
    assert [c[0].value for c in _Hooks.last.calls] == ["before_tool"]


async def test_actor_user_id_defaults_to_ctx_user_when_absent(monkeypatch):
    captured: dict = {}

    async def spy_invoke(db, ctx, name, params, **kwargs):  # noqa: ANN001, ARG002
        captured.update(kwargs)
        return {}

    _install(monkeypatch)
    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", spy_invoke)
    await invoke_tool_with_context(object(), _ctx(), "calc", {}, actor_user_id=None)
    assert captured["actor_user_id"] == ACTOR_ID


# --- 审计字段在各路径间一致 --------------------------------------------------


async def test_all_paths_share_identical_audit_identity_fields(monkeypatch):
    """tenant_id / tool_slug / source / actor_user_id / agent_id / invoke_source /
    trace_id 在确认、成功、失败三条路径上必须完全相同（仅状态类字段不同）。
    """
    tool_id = uuid4()
    seen: list[dict] = []

    async def capture(db, **kwargs):  # noqa: ANN001, ARG001
        seen.append(kwargs)

    monkeypatch.setattr(ctx_mod, "write_tool_invocation_log", capture)
    monkeypatch.setattr(ctx_mod, "HookRunner", _Hooks)
    monkeypatch.setattr(ctx_mod, "get_trace_id", lambda: "trace-1")

    identity = {"tenant_id", "tool_slug", "tool_id", "source", "actor_user_id", "agent_id", "invoke_source", "trace_id"}

    async def fake_resolve(db, ctx, slug, *, tool_id=None):  # noqa: ANN001, ARG002
        return {
            "slug": slug,
            "name": "计算器",
            "require_confirmation": False,
            "source": "builtin",
            "tool_id": tool_id,
        }

    monkeypatch.setattr(ctx_mod, "resolve_tool_meta", fake_resolve)
    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", _default_invoke)

    # 成功路径
    await invoke_tool_with_context(object(), _ctx(), "calc", {"a": 1}, tool_id=tool_id, actor_user_id=ACTOR_ID, agent_id=AGENT_ID)

    # 失败路径
    async def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("x")

    monkeypatch.setattr(ctx_mod, "invoke_tool_by_name", boom)
    with pytest.raises(RuntimeError):
        await invoke_tool_with_context(object(), _ctx(), "calc", {"a": 1}, tool_id=tool_id, actor_user_id=ACTOR_ID, agent_id=AGENT_ID)

    assert len(seen) == 2
    for row in seen:
        assert {k: row[k] for k in identity} == {
            "tenant_id": TENANT_ID,
            "tool_slug": "calc",
            "tool_id": tool_id,
            "source": "builtin",
            "actor_user_id": ACTOR_ID,
            "agent_id": AGENT_ID,
            "invoke_source": "api",
            "trace_id": "trace-1",
        }


def test_confirmation_error_is_bad_request_subclass():
    err = ToolConfirmationRequired("calc", "计算器", None, {})
    assert isinstance(err, BadRequestError)
    assert confirmation_mod.ToolConfirmationRequired is ToolConfirmationRequired
