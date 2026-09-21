"""loop 感知注册表：每个事件循环各自持有 engine，不复用别个 loop 的连接池。

本 bug 的本质：全局单例 engine 的连接池里留着上一个 loop 创建的 asyncpg 连接，
新 loop 里第一次复用即抛 ``got Future attached to a different loop``。故核心不变量
是「不同 loop ⇒ 不同 engine」。

用替身 engine/maker，不触真库；重点断言「身份」而非「没抛异常」。
"""

from __future__ import annotations

import ast
import asyncio
import inspect
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import miles_core.infra.db as db_barrel
from miles_core.infra.db import async_session as async_session_mod
from miles_core.infra.db.async_session import (
    AsyncSessionLocal,
    dispose_loop_engines,
    get_engine,
)
from tests.paths import BACKEND_ROOT


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
    """``dispose_loop_engines()`` 只释放当前 loop，且可重复调用。

    注册表是**进程级共享**的一张表：API 长命 loop 与 Worker 短命 loop 的 engine 同处其中。
    故「不波及其它 loop」这半边必须有判别力——把实现写成「清空整张表并逐个 dispose」，会顺手
    释放掉同进程别处（如 API 长命 loop）的 engine，且不会立刻报错，要等下一个请求才变成难查的
    池错误。为此顺序是「**先**在第二个 loop 上建 engine 并**持有那个 loop**（弱键条目要 key 存活
    才在），**再**回到第一个 loop dispose」；若像早先那样在 dispose 之后才创建第二个 engine，
    dispose 那一刻注册表里只有一条，清空整表 / 批量 dispose 的错版照样全绿。
    """
    built: list[tuple[int, _StubEngine]] = []
    _install_stubs(monkeypatch, built)

    async def _grab() -> _StubEngine:
        return get_engine()

    other_engine: list[_StubEngine] = []
    loop_b = asyncio.new_event_loop()  # 持有引用：弱键条目要求 key 存活才在
    try:
        other_engine.append(loop_b.run_until_complete(_grab()))

        first_engine: list[_StubEngine] = []

        async def _dispose_mine() -> None:
            first_engine.append(get_engine())
            await dispose_loop_engines()
            await dispose_loop_engines()  # 幂等：不得抛

        asyncio.run(_dispose_mine())

        assert first_engine[0].disposed == 1, "重复调用只应释放一次"
        assert other_engine[0].disposed == 0, "另一个 loop 的 engine 不得被别人的 dispose 波及"
        assert first_engine[0] is not other_engine[0], "前置条件：两个 loop 本就不该共用 engine"
        # 注册项必须**原样仍在**：清空整表 / 批量 dispose 的错版会在这里取到一个新建的 engine。
        assert loop_b.run_until_complete(_grab()) is other_engine[0], "别的 loop 的注册项不得被摘除或重建"
        assert len(built) == 2, "全过程只应构造两个 engine（B 那条未被误删后重建）"
    finally:
        # 收尾：loop_b 一直存活 ⇒ 它的注册项也一直在，得由本用例自己摘掉，免得留给别的用例。
        loop_b.run_until_complete(dispose_loop_engines())
        loop_b.close()


def test_dispose_then_reuse_builds_a_brand_new_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """dispose 之后同一 loop 再取会话是**新建 engine**，而非复用已释放的旧池。

    §7.2 说「释放后同一 loop 再取会话**仍可用**」，而「可用」的来源是实现里 ``pop`` 整条注册项
    ⇒ 下次懒建一整个 engine（含新池）。这条区分出一处真实风险边界（spec §8 已记录现象、此处把
    行为钉住）：dispose 之后继续用会话不会报错，而是**静默新建一个无人释放的 engine**——Worker
    边界之后再取会话就会重新泄漏一池。故这里断言的是「新建」这个事实，不是「不抛异常」。
    """
    built: list[tuple[int, _StubEngine]] = []
    _install_stubs(monkeypatch, built)

    async def _dispose_then_reuse() -> None:
        before = get_engine()
        await dispose_loop_engines()
        after = get_engine()
        assert after is not before, "释放是 pop 整条注册项，再取必须新建 engine，不得复用已释放的旧池"
        assert before.disposed == 1, "被释放的那份必须已 dispose（否则下面「新建」可能只是换了变量名）"
        assert AsyncSessionLocal().tag == str(id(after)), "新建 engine 之后取会话仍可用，且由新 maker 产出"

    asyncio.run(_dispose_then_reuse())
    assert len(built) == 2, "同一 loop 内 dispose 后再取会话应恰好构造两个 engine（旧的不复用）"


def test_async_session_local_is_module_function_returning_loop_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """新契约：``AsyncSessionLocal`` 是模块级函数，调用即返回本 loop maker 产出的会话。

    旧实现是 ``sessionmaker`` 实例，``callable(...)`` 对实例与函数同样成立，守不住
    「实例 → 函数」这次改动，故这里断言身份（``isfunction``）+ 行为（产物原样返回）。
    """
    assert inspect.isfunction(AsyncSessionLocal), "必须是模块级函数，而非 sessionmaker 实例"

    sentinel = object()

    monkeypatch.setattr(async_session_mod, "build_engine", lambda settings: _StubEngine())
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", lambda *a, **kw: lambda: sentinel)

    async def _use() -> None:
        assert AsyncSessionLocal() is sentinel, "必须返回本 loop maker 产出的会话"

    asyncio.run(_use())


def test_sessionmaker_receives_class_and_expire_on_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """``class_=AsyncSession`` 与 ``expire_on_commit=False`` 必须原样传给 ``async_sessionmaker``。

    ``expire_on_commit=False`` 是调用方的硬依赖：多处调用点在 commit 之后继续读实例属性
    （如 ``get_db()`` 在 yield 后 commit），一旦漂回 SQLAlchemy 默认 ``True``，那些读取会
    触发提交后的惰性刷新——在已超过会话生命周期的上下文里额外 await。
    """
    captured: dict[str, Any] = {}

    def _recording_sessionmaker(engine: Any, **kwargs: Any) -> Any:
        captured["engine"] = engine
        captured.update(kwargs)
        return lambda: None

    monkeypatch.setattr(async_session_mod, "build_engine", lambda settings: _StubEngine())
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", _recording_sessionmaker)

    async def _use() -> None:
        get_engine()

    asyncio.run(_use())

    assert captured["class_"] is AsyncSession, "会话类必须显式为 AsyncSession"
    assert captured["expire_on_commit"] is False, "调用方依赖 commit 后仍可读属性"


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


# 路径常量统一来自 ``tests.paths``：本文件在 ``tests/miles_core/infra/db/``，深度已变，
# 不能再靠 ``parents[N]`` 猜仓库根（N 会随目录层级漂移）。
_BACKEND_ROOT = BACKEND_ROOT
_HEALTH_CHECKS_SRC = _BACKEND_ROOT / "packages" / "miles-core" / "src" / "miles_core" / "utils" / "health_checks.py"


def _called_function_names(tree: ast.AST) -> set[str]:
    """语法树里所有被**调用**的函数名（裸名与属性访问都算）。

    ``get_engine()`` 与 ``db.get_engine()`` 都记作 ``get_engine``，故「换成模块属性访问」不会误报。
    判别力是**单向**的：本文件断言的是「``get_engine`` 出现在被调用名里」，故它只能证明「确实调了
    这个函数名」，不能证明「调用就挂在 ``check_postgres`` 上」——留一个同名 shim 或别处顺手调一次
    都能骗过它（要更严就得把调用与函数体绑定，成本不划算）。反向的改名/别名（`import get_engine
    as ge`）会变红，那是**可接受的误报**：它确实是接线变动，改的人顺手同步本断言即可。注释、
    docstring、字符串字面量都不是 ``ast.Call``，其中的同名文本天然免疫。
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def test_db_barrel_no_longer_exports_deleted_symbols() -> None:
    """``miles_core.infra.db`` 的导出面不得再含已删符号（spec §7.5 / §5.2）。

    §5.2 的「符号收敛」是「单一工厂」方案的落地判据：``engine`` / ``get_worker_session`` /
    ``short_db_session`` 三个名字只要还挂在 barrel 上，调用方（与照抄文档的人）就仍能走回旧机制，
    收敛只是名义上的。属性访问是**实际可达面**，``__all__`` 是**显式导出契约**，两者都钉住。
    """
    for name in ("engine", "get_worker_session", "short_db_session"):
        assert not hasattr(db_barrel, name), f"miles_core.infra.db 仍暴露已删符号 {name!r}：旧机制会随 barrel 复活"
        assert name not in db_barrel.__all__, f"miles_core.infra.db.__all__ 仍声明已删符号 {name!r}"


def test_health_checks_uses_loop_aware_engine_factory() -> None:
    """``health_checks.check_postgres`` 必须走 loop 感知的 ``get_engine()``（spec §7.5 / §5.2）。

    这是删掉模块级 ``engine`` 单例后唯一被点名的消费者接线点。若它退回单例、或自己
    ``create_async_engine``，「脚本 / 长命进程里每 loop 一池」这条失败形状就重新出现，而
    **没有任何行为用例会红**：``tests/infra/test_infra.py`` 打桩的是 ``check_postgres`` 本身，
    看不见它内部的取引擎方式。

    用 AST 而非「patch + 断言被调用」：后者要么需要真连库（打桩落空还会静默退化成恒真断言），
    要么只能看见「谁被调用」而看不见「谁没被调用」。AST 还天然免疫注释/docstring 里的同名文本。
    """
    assert _HEALTH_CHECKS_SRC.exists(), f"扫描目标不存在，护栏会空转：{_HEALTH_CHECKS_SRC}"
    tree = ast.parse(_HEALTH_CHECKS_SRC.read_text(encoding="utf-8"), filename=str(_HEALTH_CHECKS_SRC))

    assert "get_engine" in _called_function_names(tree), (
        "health_checks 必须用 get_engine()（本 loop 的 engine）；改回模块级 engine 单例或自建 engine 都会让脚本 / 长命进程每 loop 一池，而现有行为用例不会红"
    )
    imported = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert "engine" not in imported, "不得再 import 已删除的模块级 engine 单例"
