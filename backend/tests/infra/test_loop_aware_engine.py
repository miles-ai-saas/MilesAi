"""loop 感知注册表：每个事件循环各自持有 engine，不复用别个 loop 的连接池。

本 bug 的本质：全局单例 engine 的连接池里留着上一个 loop 创建的 asyncpg 连接，
新 loop 里第一次复用即抛 ``got Future attached to a different loop``。故核心不变量
是「不同 loop ⇒ 不同 engine」。

用替身 engine/maker，不触真库；重点断言「身份」而非「没抛异常」。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from miles_core.infra.db import async_session as async_session_mod
from miles_core.infra.db.async_session import (
    AsyncSessionLocal,
    dispose_loop_engines,
    get_engine,
)


class _StubEngine:
    """engine 替身：只记录 dispose 次数。"""

    def __init__(self) -> None:
        self.disposed = 0

    async def dispose(self) -> None:
        self.disposed += 1


class _StubSession:
    """session 替身：记录自己由哪个 maker 产出，供断言「用了本 loop 的 maker」。"""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def __aenter__(self) -> _StubSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _install_stubs(monkeypatch: pytest.MonkeyPatch, built: list[tuple[int, _StubEngine]]) -> None:
    """把 ``build_engine``/``async_sessionmaker`` 换成记录式替身。

    ``built`` 记录 ``(id(engine), engine)``，用于断言「两个 loop 拿到不同 engine」。
    """

    def _fake_build_engine(settings: Any) -> _StubEngine:
        engine = _StubEngine()
        built.append((id(engine), engine))
        return engine

    def _fake_sessionmaker(engine: Any, **kwargs: Any) -> Any:
        def _factory() -> _StubSession:
            return _StubSession(tag=str(id(engine)))

        return _factory

    monkeypatch.setattr(async_session_mod, "build_engine", _fake_build_engine)
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", _fake_sessionmaker)


def test_distinct_loops_get_distinct_engines(monkeypatch: pytest.MonkeyPatch) -> None:
    """本 bug 的本质：跨 loop 必须换 engine，不得复用。"""
    built: list[tuple[int, _StubEngine]] = []
    _install_stubs(monkeypatch, built)

    async def _use_in_current_loop() -> int:
        return id(get_engine())

    first = asyncio.run(_use_in_current_loop())
    second = asyncio.run(_use_in_current_loop())

    assert first != second, "两个不同的事件循环必须拿到不同的 engine（复用即跨 loop 复用连接池）"
    assert len(built) == 2


def test_same_loop_reuses_one_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一 loop 内必须复用：否则每个会话都新建一池连接。"""
    built: list[tuple[int, _StubEngine]] = []
    _install_stubs(monkeypatch, built)

    async def _use_twice() -> None:
        assert get_engine() is get_engine(), "同一 loop 内必须复用同一个 engine"

    asyncio.run(_use_twice())
    assert len(built) == 1, "一个 loop 只应构造一个 engine"


def test_session_factory_uses_current_loop_maker(monkeypatch: pytest.MonkeyPatch) -> None:
    """``AsyncSessionLocal()`` 产出的会话必须来自「本 loop」的 maker。"""
    built: list[tuple[int, _StubEngine]] = []
    _install_stubs(monkeypatch, built)

    async def _use() -> None:
        session = AsyncSessionLocal()
        assert session.tag == str(id(get_engine())), "会话必须由本 loop 的 engine 派生"

    asyncio.run(_use())


def test_dispose_only_affects_current_loop_and_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``dispose_loop_engines()`` 只释放当前 loop，且可重复调用。"""
    built: list[tuple[int, _StubEngine]] = []
    _install_stubs(monkeypatch, built)

    first_engine: list[_StubEngine] = []

    async def _dispose_mine() -> None:
        first_engine.append(get_engine())
        await dispose_loop_engines()
        await dispose_loop_engines()  # 幂等：不得抛

    asyncio.run(_dispose_mine())
    assert first_engine[0].disposed == 1, "重复调用只应释放一次"

    second_engine: list[_StubEngine] = []

    async def _other_loop() -> None:
        second_engine.append(get_engine())

    asyncio.run(_other_loop())
    assert second_engine[0].disposed == 0, "另一个 loop 的 engine 不得被别人的 dispose 波及"


def test_async_session_local_is_a_plain_callable() -> None:
    """形状不变量：``AsyncSessionLocal`` 必须仍是模块级名字（测试按属性名打桩依赖它）。"""
    assert callable(AsyncSessionLocal)


def test_engine_is_built_by_build_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """engine 必须经 ``build_engine`` 构造，不得手搓（否则池配置静默漂移）。"""
    seen: list[Any] = []
    sentinel = _StubEngine()

    def _fake_build_engine(settings: Any) -> Any:
        seen.append(settings)
        return sentinel

    monkeypatch.setattr(async_session_mod, "build_engine", _fake_build_engine)
    # 会话工厂也换成替身：本用例只观察 engine 的构造过程，不该顺带建出真 sessionmaker。
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", lambda *a, **kw: lambda: None)

    async def _use() -> None:
        assert get_engine() is sentinel

    asyncio.run(_use())
    assert seen == [async_session_mod.settings]


def test_engine_receives_configured_pool_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """池参数必须真的来自 ``Settings``。

    池参数默认值恰等于 SQLAlchemy 原默认，所以只断言默认值无法区分「接线正确」与
    「压根没传参」（两者行为完全一致）——这里断言「参数被传了」。
    """
    captured: dict[str, Any] = {}

    def _fake_create_async_engine(url: str, **kwargs: Any) -> _StubEngine:
        captured["url"] = url
        captured.update(kwargs)
        return _StubEngine()

    monkeypatch.setattr(async_session_mod, "create_async_engine", _fake_create_async_engine)
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", lambda *a, **kw: lambda: None)

    async def _use() -> None:
        get_engine()

    asyncio.run(_use())

    settings = async_session_mod.settings
    assert captured["url"] == settings.database_url
    assert captured["echo"] == settings.debug
    assert captured["pool_pre_ping"] is True
    assert captured["pool_size"] == settings.db_pool_size
    assert captured["max_overflow"] == settings.db_max_overflow
    assert captured["pool_timeout"] == settings.db_pool_timeout
