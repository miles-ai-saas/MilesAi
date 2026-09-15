"""组合不变量：真实站点在 ``get_worker_session()`` 块内/外必须用对工厂。

本分支赖以成立的那个前提，此前没有已提交测试守着：

- 逐站点护栏（各域测试文件）只断言「本模块引用了 ``short_db_session``」；
- 结构不变量（``test_no_global_session_in_worker_paths.py``）只断言「模块命名空间里没有
  ``AsyncSessionLocal``」；
- ``test_short_db_session.py`` 只覆盖 helper 自身（手工 set/reset ContextVar）。

三者都不覆盖**组合**：由 ``get_worker_session()`` 负责绑定，站点自己什么都不知道。终审
Important-1 实测：把 ``get_worker_session()`` 改成不绑定 ContextVar 后 **1081/1082 仍绿**。

本文件用替身把「站点实际用了哪个工厂」变成可观察量（而不是「没抛异常」）：
`progress.update_generative_job_progress` 是真实站点，块内必须走 worker maker、块外必须回退
全局 maker。替身只换 engine / sessionmaker 与 Redis 广播，不触真库、不触网络。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from miles_ai.integrations.generative.jobs import progress as progress_mod
from miles_core.infra.db import async_session as async_session_mod
from miles_core.infra.db.async_session import (
    _reset_worker_sessionmaker,
    _set_worker_sessionmaker,
    get_worker_session,
)


class _StubEngine:
    """``get_worker_session()`` 内新建的 worker engine 替身（只记录 dispose）。"""

    def __init__(self) -> None:
        self.disposed = 0

    async def dispose(self) -> None:
        self.disposed += 1


class _FakeSession:
    """最小会话替身：``factory`` 标明它是哪一路工厂产出的。"""

    def __init__(self, factory: str) -> None:
        self.factory = factory
        self.commits = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get(self, model: object, pk: object) -> SimpleNamespace:
        return SimpleNamespace(
            tenant_id=uuid4(),
            status=SimpleNamespace(value="running"),
            progress_percent=0,
            progress_message="",
        )

    async def commit(self) -> None:
        self.commits += 1


class _FakeMaker:
    """sessionmaker 替身：产出带 factory 标签的会话并全部记账。"""

    def __init__(self, factory: str) -> None:
        self.factory = factory
        self.sessions: list[_FakeSession] = []

    def __call__(self) -> _FakeSession:
        session = _FakeSession(self.factory)
        self.sessions.append(session)
        return session


class _Doubles:
    """一次用例的替身集合与断言助手。"""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.worker_maker = _FakeMaker("worker")
        self.global_maker = _FakeMaker("global")
        self.engines: list[_StubEngine] = []

        def _fake_create_async_engine(*args: object, **kwargs: object) -> _StubEngine:
            stub = _StubEngine()
            self.engines.append(stub)
            return stub

        def _fake_async_sessionmaker(eng: object, **kwargs: object) -> _FakeMaker:
            # worker 工厂由 get_worker_session() 现场构造，必须绑在它自己新建的 engine 上；
            # 换成全局 engine 或全局 maker 都会在这里当场暴露。
            assert eng in self.engines, "worker sessionmaker 必须绑定 get_worker_session() 新建的 engine"
            return self.worker_maker

        monkeypatch.setattr(async_session_mod, "create_async_engine", _fake_create_async_engine)
        monkeypatch.setattr(async_session_mod, "async_sessionmaker", _fake_async_sessionmaker)
        monkeypatch.setattr(async_session_mod, "AsyncSessionLocal", self.global_maker)
        # 站点的 Redis 广播不是被测对象，打桩以免触网。
        monkeypatch.setattr(progress_mod, "publish_generative_job_update", AsyncMock())

    def worker_session_factories(self) -> list[str]:
        return [s.factory for s in self.worker_maker.sessions]

    def global_session_factories(self) -> list[str]:
        return [s.factory for s in self.global_maker.sessions]


def _site(job_id: UUID | None = None, *, percent: int = 10) -> object:
    """调用真实站点（``progress.update_generative_job_progress``）。"""
    return progress_mod.update_generative_job_progress(job_id or uuid4(), percent=percent, message="composition probe")


@pytest.mark.asyncio
async def test_site_inside_worker_block_gets_the_worker_factory(monkeypatch):
    """块内：站点会话必须来自 worker maker，全局一次都不许被碰。"""
    doubles = _Doubles(monkeypatch)

    async with get_worker_session():
        await _site()

    assert len(doubles.engines) == 1, "get_worker_session() 应为本次调用新建一个 worker engine"
    assert doubles.engines[0].disposed == 1, "worker engine 必须在退出时 dispose"
    # 先断「没有回退全局」：这条失败信息最直指问题（ContextVar 没绑定时站点会静默用全局）。
    assert doubles.global_session_factories() == [], "块内站点回退全局 = 跨 loop 复用连接（本分支要修的就是它）"
    # 两次会话：块自身的那个 + 站点自己开的短会话。
    assert doubles.worker_session_factories() == ["worker", "worker"]
    assert doubles.worker_maker.sessions[1].commits == 1


@pytest.mark.asyncio
async def test_site_outside_worker_block_falls_back_to_the_global_factory(monkeypatch):
    """块外：站点必须走全局 maker——这是 API / CLI 单 loop 进程的预期路径。"""
    doubles = _Doubles(monkeypatch)
    token = _set_worker_sessionmaker(None)
    try:
        await _site()
    finally:
        _reset_worker_sessionmaker(token)

    assert doubles.engines == [], "块外不得新建 worker engine"
    assert doubles.global_session_factories() == ["global"]
    assert doubles.global_maker.sessions[0].commits == 1
    assert doubles.worker_session_factories() == []


@pytest.mark.asyncio
async def test_site_in_a_child_task_spawned_inside_the_block_keeps_the_worker_factory(monkeypatch):
    """块内 spawn 的子任务也必须拿到 worker 工厂。

    ContextVar 在 ``create_task`` / ``gather`` 时随上下文复制，而 Worker 子树的真实 spawn
    （``deepagents/orchestrator.py`` 用 ``gather`` 并行子智能体）就在这个形态上；若哪天换成
    会脱离上下文的执行方式（线程池等），本用例会红。
    """
    doubles = _Doubles(monkeypatch)

    async with get_worker_session():
        await asyncio.gather(_site(percent=1), _site(percent=2))

    assert doubles.global_session_factories() == [], "子任务里回退全局 = 上下文没被复制（本分支要修的就是它）"
    assert doubles.worker_session_factories() == ["worker", "worker", "worker"]


@pytest.mark.asyncio
async def test_context_is_restored_after_the_block(monkeypatch):
    """退出块后 ContextVar 必须复位：否则同一进程里后续请求会误用已 dispose 的 worker engine。"""
    doubles = _Doubles(monkeypatch)

    async with get_worker_session():
        await _site()
    await _site()

    assert doubles.worker_session_factories() == ["worker", "worker"]
    assert doubles.global_session_factories() == ["global"]
    assert doubles.engines[0].disposed == 1
