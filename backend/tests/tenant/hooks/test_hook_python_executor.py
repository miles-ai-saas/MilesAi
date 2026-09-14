"""``HookPythonMixin._run_python`` 的特征化测试。

该函数此前零直接覆盖（``test_python_hook.py`` 只测了 echo 插件本身）。它包含一条
**安全边界**——仅允许 import ``miles_portal.tenant.hooks.plugins.`` 前缀的模块，
避免租户配置的 ``config.module`` 变成任意代码执行入口——以及 4 处重复的
``_write_log`` 调用。本文件先锁定既有行为，作为重构安全网。
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_portal.tenant.hooks.models import HookScope, HookTrigger, HookType
from miles_portal.tenant.hooks.services.executor.service import HookExecutor

ALLOWED_MODULE = "miles_portal.tenant.hooks.plugins.fake_test_mod"


# --- 替身 -------------------------------------------------------------------


def _db():
    """记录被 ``add`` 的审计日志行。"""
    rows: list = []
    return SimpleNamespace(add=rows.append, rows=rows)


def _hook(*, config=None, name="py-hook"):
    cfg = {"module": ALLOWED_MODULE, "function": "handle"} if config is None else config
    return SimpleNamespace(id=uuid4(), name=name, hook_type=HookType.PYTHON, config=cfg)


def _binding(hook):
    return SimpleNamespace(id=uuid4(), hook=hook)


def _install_plugin(monkeypatch, fn, *, name: str = "handle", module: str = ALLOWED_MODULE):
    """把假插件放入 ``sys.modules``，使 ``importlib.import_module`` 直接命中。"""
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(**{name: fn}))
    return module


async def _run(*, hook, db, trigger=HookTrigger.BEFORE_CALL, payload=None):
    ex = HookExecutor(db, uuid4())
    return await ex._run_python(
        hook,
        binding=_binding(hook),
        trigger=trigger,
        scope=HookScope.GLOBAL,
        target_id=None,
        payload=payload if payload is not None else {"query": "原始"},
        trace_id=None,
    )


# --- 安全边界：模块路径白名单 -------------------------------------------------


@pytest.mark.parametrize("bad_module", ["os", "subprocess", "miles_portal.tenant.agents"])
async def test_rejects_module_outside_allowlist_without_importing(monkeypatch, bad_module):
    """非白名单前缀的模块必须拒绝，且绝不能触发 import（防任意代码执行）。"""
    called: list[str] = []

    def boom(name, *args, **kwargs):  # noqa: ANN001, ARG001
        called.append(name)
        raise AssertionError("不应发生 import")

    monkeypatch.setattr("importlib.import_module", boom)
    db = _db()
    item, payload = await _run(hook=_hook(config={"module": bad_module}), db=db)

    assert item == {"hook": "py-hook", "status": "error", "reason": "invalid module"}
    assert payload == {"query": "原始"}
    assert called == []
    assert db.rows[0].status == "error"
    assert db.rows[0].error_message == "invalid python module path"
    assert db.rows[0].duration_ms == 0


async def test_missing_module_config_falls_back_to_echo_default(monkeypatch):
    """未配置 module 时默认示例插件 ``plugins.echo`` + ``handle``。"""
    seen: list[str] = []
    real_import_module = importlib.import_module

    def spy(name, *args, **kwargs):  # noqa: ANN001
        seen.append(name)
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", spy)
    db = _db()
    item, _ = await _run(hook=_hook(config={}), db=db)

    assert seen == ["miles_portal.tenant.hooks.plugins.echo"]
    assert item["status"] == "ok"


async def test_empty_module_or_function_string_falls_back_to_defaults(monkeypatch):
    """空字符串是 falsy，会退回默认 module / function（而非被白名单拒绝）。"""
    seen: list[str] = []
    real_import_module = importlib.import_module

    def spy(name, *args, **kwargs):  # noqa: ANN001
        seen.append(name)
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", spy)
    db = _db()
    item, _ = await _run(hook=_hook(config={"module": "", "function": ""}), db=db)

    assert seen == ["miles_portal.tenant.hooks.plugins.echo"]
    assert item["status"] == "ok"


# --- 插件调用形态 ------------------------------------------------------------


async def test_sync_plugin_is_called(monkeypatch):
    captured: dict = {}

    def sync_handle(envelope):  # noqa: ANN001
        captured["envelope"] = envelope
        return {"action": "continue"}

    _install_plugin(monkeypatch, sync_handle)
    db = _db()
    item, _ = await _run(hook=_hook(), db=db)

    assert item["status"] == "ok"
    assert captured["envelope"]["schema_version"]  # 收到 envelope 而非裸 payload


async def test_async_plugin_is_awaited(monkeypatch):
    async def async_handle(envelope):  # noqa: ANN001, ARG001
        return {"action": "modify", "modify": {"query": "改写"}}

    _install_plugin(monkeypatch, async_handle)
    db = _db()
    item, payload = await _run(hook=_hook(), db=db)

    assert item["action"] == "modify"
    assert payload == {"query": "改写"}


async def test_missing_function_attribute_returns_error(monkeypatch):
    _install_plugin(monkeypatch, lambda env: {"action": "continue"}, name="other")  # noqa: ARG005
    db = _db()
    item, payload = await _run(hook=_hook(), db=db)

    assert item["status"] == "error"
    assert "handle" in item["reason"]
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "error"


async def test_import_failure_returns_error(monkeypatch):
    db = _db()
    item, _ = await _run(hook=_hook(config={"module": ALLOWED_MODULE + "_missing"}), db=db)
    assert item["status"] == "error"
    assert db.rows[0].status == "error"


# --- 动作：block / modify / 非 dict -------------------------------------------


async def test_block_action_blocks_before_trigger(monkeypatch):
    _install_plugin(monkeypatch, lambda env: {"action": "block", "message": "不允许"})  # noqa: ARG005
    db = _db()
    item, payload = await _run(hook=_hook(), db=db)

    assert item == {"hook": "py-hook", "status": "blocked", "message": "不允许"}
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "blocked"
    assert db.rows[0].response_action == "block"
    assert db.rows[0].error_message == "不允许"


async def test_block_action_is_not_blocking_for_after_trigger(monkeypatch):
    _install_plugin(monkeypatch, lambda env: {"action": "block", "message": "x"})  # noqa: ARG005
    db = _db()
    item, payload = await _run(hook=_hook(), db=db, trigger=HookTrigger.AFTER_CALL)

    assert item["status"] == "ok"
    assert item["action"] == "block"
    assert payload == {"query": "原始"}
    assert db.rows[0].status == "ok"


async def test_modify_action_merges_allowlisted_fields_only(monkeypatch):
    _install_plugin(monkeypatch, lambda env: {"action": "modify", "modify": {"query": "改写", "forbidden": "x"}})  # noqa: ARG005
    db = _db()
    item, payload = await _run(hook=_hook(), db=db)

    assert item["action"] == "modify"
    assert payload == {"query": "改写"}


@pytest.mark.parametrize("raw", [None, "text", 42, []])
async def test_non_dict_return_degrades_to_continue(monkeypatch, raw):
    _install_plugin(monkeypatch, lambda env: raw)  # noqa: ARG005
    db = _db()
    item, payload = await _run(hook=_hook(), db=db)

    assert item["status"] == "ok"
    assert item["action"] == "continue"
    assert payload == {"query": "原始"}


# --- 异常 -------------------------------------------------------------------


async def test_plugin_exception_returns_error_with_truncated_reason(monkeypatch):
    def boom(envelope):  # noqa: ANN001, ARG001
        raise RuntimeError("x" * 900)

    _install_plugin(monkeypatch, boom)
    db = _db()
    item, payload = await _run(hook=_hook(), db=db)

    assert item["status"] == "error"
    assert len(item["reason"]) == 200
    assert len(db.rows[0].error_message) == 500
    assert payload == {"query": "原始"}  # 失败时回退原始 payload


# --- 审计日志字段 ------------------------------------------------------------


async def test_success_writes_ok_log_reusing_parsed_action(monkeypatch):
    _install_plugin(monkeypatch, lambda env: {"action": "continue"})  # noqa: ARG005
    db = _db()
    await _run(hook=_hook(), db=db)

    row = db.rows[0]
    assert row.status == "ok"
    assert row.response_action == "continue"
    assert row.error_message is None
    assert row.duration_ms >= 0
    assert row.scope == "global"
    assert row.trigger == "before_call"
