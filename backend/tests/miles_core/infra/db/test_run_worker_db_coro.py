"""Worker 边界包装：必须在**关闭 loop 之前**释放本 loop 的 engine。

``AsyncEngine.dispose()`` 是协程，一旦 loop 关闭就无法 await；而每次 ``asyncio.run``
换 loop，不释放就会每个任务泄漏一池连接。故用「调用 dispose 时 loop 仍在运行」且
**「就是任务自己那个 loop」**两条性质一起钉住这个时序（只断言前者放得进错版实现），
而不是只看「最终是否调过」。

包装之外还有一条不变量底网：Worker 入口不得直接 ``asyncio.run``（回退它今日无任何
用例会红），见 ``test_worker_never_calls_bare_asyncio_run``。
"""

from __future__ import annotations

import ast
import asyncio
from typing import Any

import pytest

from miles_core.infra.db import async_session as async_session_mod
from miles_core.infra.db.async_session import (
    AsyncSessionLocal,
    get_engine,
    run_worker_db_coro,
)
from tests.paths import PACKAGES


def test_releases_while_loop_still_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """释放必须发生在**任务自身那个 loop** 上，且调用时 loop 仍在运行。

    只断言「有运行中的 loop」判别力不够：``finally: asyncio.run(dispose_loop_engines())``
    这种错版在新 loop 上 ``pop``，对任务自己的 loop 恒为 no-op（条目照旧泄漏，而泄漏正是
    本包装存在的唯一理由），却能让「有 loop」型断言全绿。故这里同时记下两个 loop 的身份。
    """
    seen: list[asyncio.AbstractEventLoop] = []

    async def _fake_dispose() -> None:
        # 无运行中的 loop 时直接抛 RuntimeError——这本身就是「loop 还开着」的断言。
        seen.append(asyncio.get_running_loop())

    monkeypatch.setattr(async_session_mod, "dispose_loop_engines", _fake_dispose)

    async def _work() -> str:
        seen.append(asyncio.get_running_loop())
        return "done"

    assert run_worker_db_coro(_work()) == "done"
    assert len(seen) == 2, "dispose 必须被 await 恰好一次（且发生在任务结束之后）"
    assert seen[0] is seen[1], "释放必须发生在任务自身那个 loop 上"


def test_releases_on_exception_and_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """异常路径同样释放，且异常照常传播。"""
    releases: list[str] = []

    async def _fake_dispose() -> None:
        releases.append("released")

    monkeypatch.setattr(async_session_mod, "dispose_loop_engines", _fake_dispose)

    class _Boom(Exception):
        pass

    async def _work() -> None:
        raise _Boom("任务失败")

    with pytest.raises(_Boom):
        run_worker_db_coro(_work())
    assert releases == ["released"], "任务抛异常时也必须释放，否则任务失败会连带泄漏连接"


def test_six_consecutive_runs_each_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """连续 6 次（复刻 Worker 每任务一 loop）必须每次都释放，不能只在第一次。"""
    releases: list[int] = []

    async def _fake_dispose() -> None:
        releases.append(len(releases))

    monkeypatch.setattr(async_session_mod, "dispose_loop_engines", _fake_dispose)

    async def _work() -> None:
        return None

    for _ in range(6):
        run_worker_db_coro(_work())
    assert releases == [0, 1, 2, 3, 4, 5]


def test_returns_the_coroutine_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """返回值必须原样透出（``probe_models_health`` 依赖它返回摘要字符串）。"""

    async def _fake_dispose() -> None:
        return None

    monkeypatch.setattr(async_session_mod, "dispose_loop_engines", _fake_dispose)

    async def _work() -> str:
        return "checked=3 ok=3"

    assert run_worker_db_coro(_work()) == "checked=3 ok=3"


def test_real_dispose_releases_the_current_loop_entry() -> None:
    """端到端（**不打桩** ``dispose_loop_engines``）：包装与真释放的接线必须成立。

    上面四条用例把 ``dispose_loop_engines`` 全换成了替身，只看得见「它被调过」；真释放
    少 await 一次、``pop`` 错 key、或压根只是改了字典视图，替身法一律看不见。这里让真
    ``dispose_loop_engines()`` 跑一次（真 engine、真 pool，但不连库），把接线钉住。

    判别力依赖两点，缺一不可：① 用例自己持有 loop 引用（``captured["loop"]``），否则
    loop 被回收后弱键条目会自行消失，断言就白测了；② 断言 engine 的池对象被换掉——
    只 ``pop`` 不 await ``dispose()`` 的实现不会换池（``Engine.dispose()`` 文档：旧池
    被 dispose 后**立即新建一个池**）。
    """
    captured: dict[str, Any] = {}
    # 前置基线而非「必须为空」：别的用例（异步 fixture）可能留下 loop 仍存活的条目，
    # 那是它们的事；本用例只要求自己这条 loop 不留残留。
    # 读的是私有字典 ``_loop_engines``：「当前 loop 有无注册项」没有公开查询接口。
    before = set(async_session_mod._loop_engines.keys())

    async def _work() -> None:
        captured["loop"] = asyncio.get_running_loop()
        captured["engine"] = get_engine()  # 真实建 engine，登记进当前 loop
        captured["pool"] = captured["engine"].pool  # dispose 前的池，用于证明真释放跑过
        async with AsyncSessionLocal() as session:  # 顺带证明会话可用
            await session.rollback()

    run_worker_db_coro(_work())

    assert captured["loop"].is_closed(), "loop 已关闭——证明「run 之后再 dispose」不可能成功"
    after = set(async_session_mod._loop_engines.keys())
    assert captured["loop"] not in after, "释放是 pop 整条注册项，跑完不得留残留"
    assert after <= before, "包装只管自己的 loop，不得额外登记别的条目"
    # ``engine.pool`` 是公开属性；池身份变化证明真 await 了 ``Engine.dispose()``（只 pop 字典不会换池）。
    assert captured["engine"].pool is not captured["pool"], "真 dispose 会换掉整个池；池对象没变说明只 pop 了字典、没真 await dispose()"


_WORKER_SRC_ROOT = PACKAGES / "miles-worker" / "src"

# 直接起事件循环、绕过包装的两个入口调用（``run`` 是 ``asyncio.run`` 的本名）。
_ASYNC_RUN_CALLS = ("run", "run_until_complete")


def _bare_asyncio_run_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """语法树里所有「直接起 loop」的调用：``(行号, 写法)``。

    三种写法都要抓：``asyncio.run(...)``、``import asyncio as aio`` 后的 ``aio.run(...)``、
    以及 ``from asyncio import run [as ...]`` 后的裸名调用。判据是**本模块内**的绑定名，
    故 ``loop.run_until_complete(...)``（别的东西起 loop）与恰好叫 ``run`` 的本地函数不计入。

    注释、docstring、字符串字面量都不是 ``ast.Call``，故其中的同名文本天然免疫。
    """
    module_aliases: set[str] = set()
    call_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_aliases.update(alias.asname or "asyncio" for alias in node.names if alias.name == "asyncio")
        elif isinstance(node, ast.ImportFrom) and node.module == "asyncio":
            call_aliases.update(alias.asname or alias.name for alias in node.names if alias.name in _ASYNC_RUN_CALLS)

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.attr in _ASYNC_RUN_CALLS and func.value.id in module_aliases:
                found.append((node.lineno, f"{func.value.id}.{func.attr}(...)"))
        elif isinstance(func, ast.Name) and func.id in call_aliases:
            found.append((node.lineno, f"{func.id}(...)"))
    return found


def test_worker_never_calls_bare_asyncio_run() -> None:
    """Worker 入口不得直接 ``asyncio.run``，必须走 ``run_worker_db_coro``。

    扫描根：``packages/miles-worker/src/**/*.py``（由本文件路径推导，见 ``_WORKER_SRC_ROOT``，
    不写死绝对路径）。扫整个包而非三个入口文件：判据是「本包任何模块」，这样新加的任务
    入口自动进网——按「当时改过哪几个文件」维护的清单必然漏站点。

    为什么这条必须存在：``tasks/generative.py`` / ``tasks/agent_schedule.py`` /
    ``tasks/model_health.py`` 任一被回退成 ``asyncio.run(...)``，全仓一千余条测试**没有一条**
    会红（打桩用例只看见包装被调用，回归者可以两个都调用）；本次迁移暂时只靠人工 ``rg``
    守着，而人工守不住。裸 ``asyncio.run`` 无法在 loop 关闭前 await ``engine.dispose()``，
    于是每个任务泄漏一池连接——正是本任务要消灭的 bug。

    用 AST 不用正则：注释/docstring 里的同名文本不得计入。扫描根今日对 ``asyncio`` 零命中，
    故无 allowlist；将来真需要放开某处，必须在此显式登记并说明它为何不需要释放。
    """
    # 探针自检：否则「零命中」无法区分「真的干净」与「探针坏了」。
    probe = ast.parse(
        "import asyncio\n"
        "import asyncio as aio\n"
        "from asyncio import run as run_async\n"
        "asyncio.run(a)\n"
        "aio.run_until_complete(b)\n"
        "run_async(c)\n"
        "loop.run_until_complete(d)\n"
        "# asyncio.run(注释里的不算)\n"
        'TEXT = "asyncio.run(字符串里的不算)"\n'
    )
    assert len(_bare_asyncio_run_calls(probe)) == 3, "探针必须抓到属性访问/别名/裸名三种真实写法"

    violations: list[str] = []
    scanned = 0
    for path in sorted(_WORKER_SRC_ROOT.glob("**/*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations += [f"{path.relative_to(_WORKER_SRC_ROOT)}:{lineno} 调用 {form}" for lineno, form in _bare_asyncio_run_calls(tree)]

    # 与上面的探针自检互补：探针保证「匹配器没坏」，这条保证「没扫到空目录」。少了它，
    # 一旦扫描根改名/搬迁，glob 返回空集，护栏就会以「零违规」永远绿。
    assert scanned >= 1, f"扫描根下没扫到任何 .py，护栏会空转：{_WORKER_SRC_ROOT}"

    assert not violations, (
        "Worker 入口不得直接 asyncio.run：它没法在 loop 关闭前 await AsyncEngine.dispose()，"
        "会每个任务泄漏一池连接。请改用 miles_core.infra.db.run_worker_db_coro。违规点：\n" + "\n".join(violations)
    )
