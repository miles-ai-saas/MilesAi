"""Worker 边界包装：必须在**关闭 loop 之前**释放本 loop 的 engine。

``AsyncEngine.dispose()`` 是协程，一旦 loop 关闭就无法 await；而每次 ``asyncio.run``
换 loop，不释放就会每个任务泄漏一池连接。故用「调用 dispose 时是否有运行中的 loop」
钉住这个时序，而不是只看「最终是否调过」。
"""

from __future__ import annotations

import asyncio

import pytest

from miles_core.infra.db import async_session as async_session_mod
from miles_core.infra.db.async_session import run_worker_db_coro


def test_releases_while_loop_still_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """释放必须发生在 loop 关闭前：调用时必须有运行中的 loop。"""
    observed: list[bool] = []

    async def _fake_dispose() -> None:
        try:
            asyncio.get_running_loop()
            observed.append(True)
        except RuntimeError:
            observed.append(False)

    monkeypatch.setattr(async_session_mod, "dispose_loop_engines", _fake_dispose)

    async def _work() -> str:
        return "done"

    assert run_worker_db_coro(_work()) == "done"
    assert observed == [True], "dispose 必须在 loop 关闭之前被 await"


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
