# Loop 感知 DB 引擎与会话工厂 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `AsyncSessionLocal()` 自身按当前事件循环取 engine，从而删除 `get_worker_session` / `short_db_session` / ContextVar 这套「按站点选工厂」的机制，并用 Worker 边界包装统一释放旧 loop 的 engine。

**Architecture:** `miles_core/infra/db/async_session.py` 里以 **loop 对象**为键的 `WeakKeyDictionary` 缓存每 loop 的 `(engine, sessionmaker)`；`AsyncSessionLocal` 由 sessionmaker 实例改为模块级**函数**（调用写法不变）；新增 `get_engine()` 与 `dispose_loop_engines()`；Worker 侧新增只负责 DB 的 `run_worker_db_coro(coro)`，在 `asyncio.run` 关闭 loop **之前** `await dispose_loop_engines()`。

**Tech Stack:** Python 3.11+、SQLAlchemy 2.x（async）、asyncpg、Celery、pytest + pytest-asyncio（`asyncio_mode = "auto"`）。

**设计依据：** `docs/superpowers/specs/2026-09-15-loop-aware-db-engine-design.md`（下称 spec）

## Global Constraints

- 所有命令在 `backend/` 下执行，且必须用 `uv run --all-packages --group dev ...`
  —— 裸 `uv run` / `uv sync` 会卸载工作区其余成员包。
- 提交前门禁（五条）：`ruff format --check .`、`ruff check .`、`lint-imports`、
  `python -m miles_server.scripts.export_openapi --check`、`python -m pytest -q`。
  基线：**1090 passed**；warning 数不在此写死——它随 `-W` 过滤器与用例改动而变
  （默认过滤器下今日全量无 warnings summary，`-W default` 下另有若干既有 ResourceWarning）。
- 测试输出保持干净：不得新增 warning。
- commit message 用**简体中文** + Conventional Commits，HEREDOC 传递。
- 分层约束：`miles_ai` ✗→ `miles_portal`；`miles_portal` ✗→ `miles_admin`；
  `miles_core` ✗→ `miles_ai`。`run_worker_db_coro` 放 `miles_core.infra.db`，worker 可引用。
- 不新增依赖（**不得引入 uvloop**；本设计按标准 asyncio loop 编写）。
- 不改 API 路由 / 响应字段 / OpenAPI 快照。
- **Redis 不进 DB 的释放路径**：`get_redis()` / `reset_redis()` 原样保留，
  `run_worker_db_coro` 不 import `miles_core.infra.redis`（spec §4 非目标）。
- 已实测确认的两个前提（无需再验证）：
  1. 标准 asyncio loop 对象可作 `WeakKeyDictionary` 键；
  2. `AsyncSessionLocal` 改为「返回 `AsyncSession` 的函数」后，既有
     `async with AsyncSessionLocal() as s:` 写法照常可用，`expire_on_commit=False` 保持。

## 任务总览

| Task | 交付物 | 为何可独立评审 |
|---|---|---|
| 1 | loop 感知注册表 + `engine`→`get_engine()` + 旧机制塌缩为转发 | 核心机制；评审者可只针对「注册表设计」否决 |
| 2 | `run_worker_db_coro` + 3 个 Celery 入口迁移 | 资源释放策略；可独立于 Task 1 否决 |
| 3 | 退役转发壳 + 18 处调用点回归 + 旧护栏解散 | 无行为变更的收尾清理，评审重点是「改全了、拆干净了」 |
| 4 | 终检：真库端到端 + 门禁 + spec 修订 | 验证与记述 |

**顺序是硬约束**：Task 2 依赖 Task 1 的 `dispose_loop_engines`；Task 3 依赖 Task 2（否则删掉
`get_worker_session` 时 `agent_schedule` 还没换掉）。每个 Task 结束时仓库都必须是绿的。

**Task 1 的边界（重要）**：Task 1 **不做** 18 处调用点的迁移，也不删 `get_worker_session` /
`short_db_session` 这两个名字——它只让它们**退化为纯转发**（见 Task 1 Step 3）。这样好处是全程
只有一条 engine 创建路径，不会出现「两个真相源」的中间态；代价是 Task 1 需同步处理三个受影响的
测试文件（Step 5）。

---

### Task 1: loop 感知注册表 + 符号收敛

> **实施期修正（已完成，勿再照抄本节内的旧措辞）**：原设计称「`WeakKeyDictionary` 的弱键让
> loop 回收即自动摘除」。实施后实测确认该说法**错误**：`asyncpg/connection.py:65` 的
> `self._loop = loop` 是强引用，池又强持有连接（`asyncpg/pool.py:343,454`），而注册表对 value
> 持强引用，故「注册表 → engine → 池 → 连接 → loop」钉住 weak key —— 只要有存活连接，条目永不
> 失效。**`dispose_loop_engines()` 是唯一释放路径**，不是可选优化。
> 代码已按此改写（`async_session.py` 模块 docstring 与 `_loop_engines` 注释），spec §5/§8 亦已
> 同步。下方 Step 3 的代码块已更新；本节 Step 7 的 commit message 保留了 `8582a5fb` 提交时的
> 原文（含旧措辞），作为历史记录不再改动。

**Files:**
- Modify: `packages/miles-core/src/miles_core/infra/db/async_session.py`（见 Step 3）
- Modify: `packages/miles-core/src/miles_core/infra/db/__init__.py`
- Modify: `packages/miles-core/src/miles_core/utils/health_checks.py:13,36`
- Modify: `backend/tests/infra/test_db_pool_settings.py`
- Create: `backend/tests/infra/test_loop_aware_engine.py`
- Delete: `backend/tests/infra/test_short_db_session.py`
- Delete: `backend/tests/infra/test_worker_session_composition.py`

**Interfaces:**
- Consumes: 无（本 Task 是起点）。沿用既有 `build_engine(settings)` 与 `settings`。
- Produces（后续 Task 依赖的确切签名）：
  - `get_engine() -> AsyncEngine` —— 当前 loop 的 engine（懒建）
  - `AsyncSessionLocal() -> AsyncSession` —— 当前 loop 的会话
  - `async def dispose_loop_engines() -> None` —— 释放**当前 loop** 的 engine
  - `_loop_engine_and_maker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]`（私有）
  - 仍保留但**已退化为转发**：`get_worker_session()`、`short_db_session()` —— 两者都只是
    `async with AsyncSessionLocal()` 的薄包装（调用点仍在 18 处，Task 3 统一改掉后删除）。
  - 保留不变：`get_db()`、`build_engine(settings)`、`get_sync_db()`
  - 删除：`engine`（模块级常量）、`_worker_sessionmaker`、`_set_worker_sessionmaker`、
    `_reset_worker_sessionmaker`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/infra/test_loop_aware_engine.py`：

```python
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
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", lambda *a, **kw: (lambda: None))

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
    monkeypatch.setattr(async_session_mod, "async_sessionmaker", lambda *a, **kw: (lambda: None))

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
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/infra/test_loop_aware_engine.py -q
```
Expected: collection error —— `ImportError: cannot import name 'get_engine'`（或 `dispose_loop_engines`）。若报别的错，先解决收集问题再继续。

- [ ] **Step 3: 实现注册表**

把 `packages/miles-core/src/miles_core/infra/db/async_session.py` 改成下面的样子。改动分两处：**文件头**（模块 docstring + import 段 + 用注册表替换 `engine = build_engine(settings)` 与 `AsyncSessionLocal = async_sessionmaker(...)` 这两行），以及**文件尾**（`get_worker_session` / `short_db_session` 塌缩为纯转发，并删掉 `_worker_sessionmaker` 三个符号）。中间的 `get_db()` 形状不变：

```python
"""异步 PostgreSQL 引擎与会话（FastAPI 主路径）。

引擎按**事件循环**持有：Celery 任务入口每次 ``asyncio.run`` 都新建 loop，若复用绑在
旧 loop 上的连接池，会抛 ``got Future attached to a different loop``。以 loop 对象为
键（``WeakKeyDictionary``；弱键只规避 id(loop) 复用，**不提供自动清理**——见下方「实施期修正」）懒建 engine，
使 ``AsyncSessionLocal()`` 对调用方而言与 loop 无关。
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from weakref import WeakKeyDictionary

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from miles_core.config import Settings, get_settings

settings = get_settings()


def build_engine(settings: Settings) -> AsyncEngine:
    """按 ``Settings`` 构造异步引擎。

    抽成函数是为了可测：池参数的默认值恰好等于 SQLAlchemy 原默认，若只在模块级
    内联构造，「接线正确」与「压根没传参」在默认配置下无法区分（行为完全一致）。
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )


# 每事件循环一份 (engine, sessionmaker)。键是 loop 对象本身而非 id(loop)：
# id 在 loop 被回收后可能被新 loop 复用，会导致误用指向已关闭 loop 的 engine。
_loop_engines: WeakKeyDictionary[
    asyncio.AbstractEventLoop, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
] = WeakKeyDictionary()


def _loop_engine_and_maker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """当前 loop 的 (engine, sessionmaker)；缺失则懒建并登记。

    无运行中的事件循环时 ``get_running_loop()`` 抛 ``RuntimeError``——这是有意为之：
    会话本就只能在 async 上下文里取用，早失败好过等到 await 时才炸。
    """
    loop = asyncio.get_running_loop()
    entry = _loop_engines.get(loop)
    if entry is None:
        engine = build_engine(settings)
        entry = (engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False))
        _loop_engines[loop] = entry
    return entry


def get_engine() -> AsyncEngine:
    """当前事件循环的 engine（懒建）。"""
    return _loop_engine_and_maker()[0]


def AsyncSessionLocal() -> AsyncSession:
    """当前事件循环的会话。

    签名与旧 ``sessionmaker`` 调用一致（返回 ``AsyncSession``，``expire_on_commit=False``），
    故既有 ``async with AsyncSessionLocal() as session:`` 写法无需改动。
    """
    return _loop_engine_and_maker()[1]()


async def dispose_loop_engines() -> None:
    """释放**当前 loop** 的 engine（由 worker 边界在关闭 loop 之前调用）。

    幂等：无条目或已释放时为空操作。释放是 ``pop`` 整条注册项，故同一 loop 再取会话会
    **新建一个 engine**（新池，由同一 ``Settings`` 快照重建），而不是复用已释放的旧池。
    必须在 loop 关闭前 await——``AsyncEngine.dispose()`` 是协程，loop 关了就无法执行；
    而每次 ``asyncio.run`` 换 loop，不释放就会每个任务泄漏一池连接。
    """
    loop = asyncio.get_running_loop()
    entry = _loop_engines.pop(loop, None)
    if entry is not None:
        await entry[0].dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """请求级会话：正常结束自动 commit，异常 rollback。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_worker_session() -> AsyncIterator[AsyncSession]:
    """Celery Worker 专用会话。

    引擎已按事件循环持有（见 ``_loop_engine_and_maker``），故不再需要另建 worker engine，
    也无需把 sessionmaker 绑到 ContextVar：直接转发 ``AsyncSessionLocal()`` 即与当前 loop 对齐。
    """
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def short_db_session() -> AsyncIterator[AsyncSession]:
    """开一个短独立会话（与调用方事务无关）。

    引擎已按事件循环持有，故 Worker 与 API / 脚本走同一条路径。
    """
    async with AsyncSessionLocal() as session:
        yield session
```

**本步一并塌缩旧机制**（这正是「单一工厂」的落点）：`_worker_sessionmaker` 及
`_set_worker_sessionmaker` / `_reset_worker_sessionmaker` 全部删除，`get_worker_session` /
`short_db_session` 退化为上面这样的纯转发。这样做的好处是**全程只有一条 engine 创建路径**
（`_loop_engine_and_maker`），不存在「两个真相源」，也不会留下指向已删符号的陈旧 docstring；
代价是本步必须同步处理两个以旧机制为主题的测试文件（见 Step 5）。

- [ ] **Step 4: 同步导出与唯一消费者**

`packages/miles-core/src/miles_core/infra/db/__init__.py` 改为：

```python
"""PostgreSQL 连接与会话。

FastAPI 依赖 get_db（异步）；Celery/ingest 使用 get_sync_db（同步）。
"""

from miles_core.infra.db.async_session import (
    AsyncSessionLocal,
    dispose_loop_engines,
    get_db,
    get_engine,
    get_worker_session,
    short_db_session,
)
from miles_core.infra.db.base import Base
from miles_core.infra.db.sync import SyncSessionLocal, get_sync_db, sync_engine

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "SyncSessionLocal",
    "dispose_loop_engines",
    "get_db",
    "get_engine",
    "get_sync_db",
    "get_worker_session",
    "short_db_session",
    "sync_engine",
]
```

`packages/miles-core/src/miles_core/utils/health_checks.py:13` 改为：

```python
from miles_core.infra.db import get_engine
```

同文件 `:36` 的 `async with engine.connect() as conn:` 改为：

```python
        async with get_engine().connect() as conn:
```

- [ ] **Step 5: 让受影响的既有测试与新语义对齐**

旧机制塌缩后，三个既有测试文件的内容与新语义不再匹配。逐个处理：

**(a) `backend/tests/infra/test_db_pool_settings.py`**

- 第 16 行的 import 由
  `from miles_core.infra.db.async_session import build_engine, engine, get_worker_session`
  改为
  `from miles_core.infra.db.async_session import build_engine, get_engine`
- 前三个用例（`test_pool_size_follows_settings` / `test_max_overflow_follows_settings` /
  `test_pool_timeout_follows_settings`）原本读模块级 `engine`；`engine` 已不存在，且
  `get_engine()` 必须在运行中的 loop 里调用。把它们改成 async 并改用 `get_engine()`，
  例如：

```python
@pytest.mark.asyncio
async def test_pool_size_follows_settings():
    assert get_engine().pool.size() == get_settings().db_pool_size
```

（`test_max_overflow_follows_settings`、`test_pool_timeout_follows_settings` 同样处理，
只换被断言的属性。）
- 末尾两个以 `get_worker_session()` 为主题的用例
  （`test_worker_engine_is_built_by_build_engine`、`test_worker_engine_receives_configured_pool_params`）
  连同 `_StubEngine` / `_StubSession` / `_stub_maker` 一并删除：worker 不再另建 engine，
  这两个用例守护的对象已不存在。它们的内核（「engine 必须经 `build_engine` 构造」
  「池参数真的来自 `Settings`」）改由 Step 1 新增文件里的
  `test_engine_is_built_by_build_engine` 与 `test_engine_receives_configured_pool_params`
  接管——见下方 (c)。

**(b) 删除两个以旧机制为主题的文件**

```bash
git rm tests/infra/test_short_db_session.py tests/infra/test_worker_session_composition.py
```

- `test_short_db_session.py`：全部断言都以 `_set_worker_sessionmaker` /
  `_reset_worker_sessionmaker` 手工绑/解 ContextVar 为前提，符号已删除、选择逻辑已不存在。
- `test_worker_session_composition.py`：主题是「真实站点在 `get_worker_session()` 块内/块外
  必须用对工厂」。塌缩后只剩一条路径，「用对工厂」不再是可观察量。它守护的实质目标
  （Worker 路径不复用别个 loop 的连接）在本次改动后由**构造保证**——`AsyncSessionLocal()`
  本身按 loop 取 engine——而非由 ContextVar 转发保证，故无需替代测试。

**(c) 无需追加新用例**

(a) 中删掉的两个 worker 用例，其内核已由 Step 1 文件里的
`test_engine_is_built_by_build_engine` 与 `test_engine_receives_configured_pool_params`
接管——那两条从 Step 1 就写好了，正是本 Task 的 TDD 红→绿对象。

- [ ] **Step 6: 跑测试与门禁**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/infra/ -q
```
Expected: 全绿（新文件 7 个用例 + `test_db_pool_settings.py` 剩余用例）。

Run（全量）:
```bash
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。**测试数不再是简单的 +5**，按下列口径核对：
1090（基线）**+7**（`test_loop_aware_engine.py` 新增）**−2**（`test_short_db_session.py`）
**−4**（`test_worker_session_composition.py`）**−2**（`test_db_pool_settings.py` 删掉的
worker 用例）**= 1089**。若实测不等于 1089，逐条查清差额来源（用例数量会随文件实际内容
浮动，关键是**没有失败、且差额可解释**），不要直接改期望值。

Run（其余四条）:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check
```
Expected: 全部通过。

- [ ] **Step 7: Commit**

```bash
git add packages/miles-core/src/miles_core/infra/db/async_session.py \
        packages/miles-core/src/miles_core/infra/db/__init__.py \
        packages/miles-core/src/miles_core/utils/health_checks.py \
        tests/infra/
git commit -F - <<'EOF'
feat(db): 引擎按事件循环持有，AsyncSessionLocal 改为 loop 感知函数

Celery 任务入口每次 asyncio.run 都新建 loop，而 engine 是模块级单例：池里留着
上一个 loop 创建的 asyncpg 连接，新 loop 第一次复用即抛「got Future attached to
a different loop」（真库实测连续 6 次调用第 2/4/6 次失败）。

改为以 loop 对象为键懒建 engine（WeakKeyDictionary，loop 回收即摘除；不用 id(loop)
以免 id 复用后误用指向已关闭 loop 的 engine）。AsyncSessionLocal 由 sessionmaker
实例改为模块级函数，调用写法不变，故调用方不必知道自己在 Worker 还是 API 里。

engine 随之收敛为 get_engine()，唯一消费者 health_checks 已同步。

旧机制的落点一并清理：get_worker_session / short_db_session 退化为纯转发，
_worker_sessionmaker 三个符号删除——全程只剩一条 engine 创建路径，不留两个真相源。
以旧机制为主题的两个测试文件随之删除，其守护的实质目标（Worker 不复用别个 loop 的
连接）此后由构造保证；池参数接线断言接到新机制上。
EOF
```

---

### Task 2: Worker 边界统一释放

**Files:**
- Modify: `packages/miles-core/src/miles_core/infra/db/async_session.py`（新增 `run_worker_db_coro`）
- Modify: `packages/miles-core/src/miles_core/infra/db/__init__.py`（导出）
- Modify: `packages/miles-worker/src/miles_worker/tasks/generative.py:22-28`
- Modify: `packages/miles-worker/src/miles_worker/tasks/agent_schedule.py:34,84`
- Modify: `packages/miles-worker/src/miles_worker/tasks/model_health.py:71`
- Create: `backend/tests/infra/test_run_worker_db_coro.py`

**Interfaces:**
- Consumes（来自 Task 1）：`dispose_loop_engines() -> None`（async、幂等）、`AsyncSessionLocal() -> AsyncSession`、`get_engine() -> AsyncEngine`
- Produces（Task 3 依赖）：`run_worker_db_coro(coro: Coroutine[Any, Any, Any]) -> Any`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/infra/test_run_worker_db_coro.py`：

```python
"""Worker 边界包装：必须在**关闭 loop 之前**释放本 loop 的 engine。

``AsyncEngine.dispose()`` 是协程，一旦 loop 关闭就无法 await；而每次 ``asyncio.run``
换 loop，不释放就会每个任务泄漏一池连接。故用「调用 dispose 时是否有运行中的 loop」
钉住这个时序，而不是只看「最终是否调过」。
"""

from __future__ import annotations

import asyncio
from typing import Any

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
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/infra/test_run_worker_db_coro.py -q
```
Expected: `ImportError: cannot import name 'run_worker_db_coro'`。

- [ ] **Step 3: 实现包装并导出**

在 `async_session.py` 的 `dispose_loop_engines()` 之后追加：

```python
def run_worker_db_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    """Worker 入口用：跑 ``coro`` 并在**关闭 loop 之前**释放本 loop 的 engine。

    释放必须发生在 loop 关闭前——``AsyncEngine.dispose()`` 是协程，loop 关了就无法
    await；而每次 ``asyncio.run`` 换 loop，不释放就会每个任务泄漏一池连接。

    只负责 DB：Redis 有自己的 ``get_redis()`` 自愈机制与 ``reset_redis()`` 清理，
    语义不同（那个漏了也不错），不并入此处。
    """

    async def _main() -> Any:
        try:
            return await coro
        finally:
            await dispose_loop_engines()

    return asyncio.run(_main())
```

并把模块顶部的 `from typing import Any` 与 `import asyncio` 就位（若 Step 3 的注已改为顶层 import）；`Coroutine` 从 `collections.abc` 导入，即顶部改为：

```python
import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import Any
from weakref import WeakKeyDictionary
```

`__init__.py` 的 import 块与 `__all__` 各加一行 `run_worker_db_coro`（按字母序插在 `get_worker_session` 之后 / `short_db_session` 之前的位置按现有排序风格放）。

- [ ] **Step 4: 迁移 3 个 Celery 入口**

`packages/miles-worker/src/miles_worker/tasks/generative.py`：

- import 区把 `from miles_core.infra.redis import reset_redis` 保留；新增
  `from miles_core.infra.db import run_worker_db_coro`
- `:22-28` 的 `_run_coro` 改为：

```python
def _run_coro(coro) -> None:
    """在独立事件循环中跑异步任务；DB engine 由包装在关闭 loop 前释放。"""
    try:
        run_worker_db_coro(coro)
    finally:
        reset_redis()
```

`packages/miles-worker/src/miles_worker/tasks/agent_schedule.py`：

- import 区 `from miles_core.infra.db import get_sync_db, get_worker_session` 改为
  `from miles_core.infra.db import AsyncSessionLocal, get_sync_db, run_worker_db_coro`
- `:34` 的 `async with get_worker_session() as db:` 改为 `async with AsyncSessionLocal() as db:`
- `:84` 的 `asyncio.run(_run_schedule_async(UUID(schedule_id)))` 改为
  `run_worker_db_coro(_run_schedule_async(UUID(schedule_id)))`
- 确认 `import asyncio` 若不再被该文件使用则删除（先 `rg -n "asyncio" <file>` 确认）。

`packages/miles-worker/src/miles_worker/tasks/model_health.py`：

- import 区新增 `from miles_core.infra.db import run_worker_db_coro`
- `:71` 的 `return asyncio.run(_probe_models_async())` 改为
  `return run_worker_db_coro(_probe_models_async())`
- 同样先确认 `asyncio` 是否仍被使用。

> `tasks/ingest.py` **不改**：它走同步引擎 `get_sync_db`，不涉及事件循环。

- [ ] **Step 5: 跑测试与门禁**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/infra/test_run_worker_db_coro.py -q
```
Expected: 4 passed。

Run:
```bash
uv run --all-packages --group dev python -m pytest -q && \
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check
```
Expected: **1094 passed**（Task 1 结束时为 1090——计划原本按 1089 推算，
Task 1 修复轮把一条近恒真用例拆成两条而 +1；1090 + 4 = 1094），其余四条通过。
warning 不写死：判据是「不得**新增**」，做对照时用相同的 `-W` 过滤器，
本 Task 实测默认过滤器下无 warnings summary（收口后全量为 1096，见 Task 2 修复轮）。

- [ ] **Step 6: Commit**

```bash
git add packages/miles-core/src/miles_core/infra/db/async_session.py \
        packages/miles-core/src/miles_core/infra/db/__init__.py \
        packages/miles-worker/src/miles_worker/tasks/generative.py \
        packages/miles-worker/src/miles_worker/tasks/agent_schedule.py \
        packages/miles-worker/src/miles_worker/tasks/model_health.py \
        tests/infra/test_run_worker_db_coro.py
git commit -F - <<'EOF'
feat(worker): 入口统一在关闭 loop 前释放 DB engine

每次 asyncio.run 换 loop 即每个任务新建一个 engine，旧 engine 的连接池若不释放
就按任务数累积泄漏。engine.dispose() 是协程，必须赶在 loop 关闭前 await——放在
asyncio.run 之后（reset_redis 现在的做法）已经关不掉了。

新增只负责 DB 的 run_worker_db_coro 包装，3 个异步 Celery 入口统一改用；它不并入
Redis 的清理，两者语义不同（Redis 客户端自愈，漏了也不错）。agent_schedule 一并
由 get_worker_session 改用 AsyncSessionLocal——注册表已让后者 loop 安全。
EOF
```

---

### Task 3: 退役转发壳、调用点回归统一工厂、旧护栏解散

> **本 Task 的性质与前一版计划不同**：Task 1 已把 `get_worker_session` / `short_db_session`
> 塌缩为 `async with AsyncSessionLocal()` 的纯转发，因此本 Task **没有行为变更**——它退掉的
> 是一层已无信息的间接引用，以及只服务于旧机制的测试机件。正因如此，它的风险很低，评审重点
> 应放在「调用点是否全部改到、护栏拆得是否干净且未误伤」。
**Files:**
- Modify: `packages/miles-core/src/miles_core/infra/db/async_session.py`（删两个转发壳）
- Modify: `packages/miles-core/src/miles_core/infra/db/__init__.py`
- Modify（13 个模块，共 18 处 `short_db_session` 调用点，见 Step 2 清单）
- Modify（3 个模块，共 4 处 `get_worker_session` 调用点：`agent_schedule.py:33`、
  `model_health.py:27`、`job_execution.py:122`、`:192`——Task 2 按方案 B 把工厂切换顺延到了本
  Task，见 Step 2b）
- Modify（13 个测试文件，撤掉 `_Boom`/`short_db_session` 机件，见 Step 4 清单）
- Delete: `backend/tests/infra/test_no_global_session_in_worker_paths.py`

**Interfaces:**
- Consumes：Task 1 的 `AsyncSessionLocal()` / `get_engine()`；Task 2 的 `run_worker_db_coro()`
- Produces：无新符号——本 Task 是**删除**。结束时 `miles_core.infra.db` 只剩
  `AsyncSessionLocal`（函数）、`get_engine`、`dispose_loop_engines`、`run_worker_db_coro`、
  `get_db`、`get_sync_db`、`Base`、`SyncSessionLocal`、`sync_engine`。

- [ ] **Step 1: 先确认调用面（删除前的事实核对）**

Run:
```bash
rg -n "short_db_session|get_worker_session" --type py packages/
```
Expected: 18 处 `async with short_db_session()` 调用点与它们的 import；**另有 4 处
`get_worker_session`**（`agent_schedule.py:33`、`model_health.py:27`、
`job_execution.py:122`、`:192`），它们是 Task 2 方案 B 有意顺延到本 Task 的工厂切换——
**不是**迁移不完整，按 Step 2b 一并处理。除此之外若还有别的 `get_worker_session` 命中，
**停下报告**。

Run:
```bash
rg -n "async with short_db_session\(\)" --type py packages/ | wc -l
```
Expected: `18`。若不符，**停下报告**——spec 的调用面统计有遗漏，需重新裁决。

- [ ] **Step 2: 回退 18 处调用点**

逐处把 `async with short_db_session() as <var>:` 改为 `async with AsyncSessionLocal() as <var>:`，
import 由 `from miles_core.infra.db import short_db_session` 改为
`from miles_core.infra.db import AsyncSessionLocal`；若该文件还从 `miles_core.infra.db`
导入别的符号，合并进同一行括号。

清单（模块 → 站点行号；行号仅作定位，**以符号为准**，改动后行号会漂）：

| 模块 | 站点 |
|---|---|
| `miles_ai/integrations/langgraph/graphs/rag_qa.py` | `:67` |
| `miles_ai/integrations/generative/jobs/progress.py` | `:54`、`:75` |
| `miles_ai/flow_runtime/nodes/rag_nodes.py` | `:48` |
| `miles_ai/flow_runtime/nodes/image_generate.py` | `:55`、`:84` |
| `miles_ai/flow_runtime/nodes/video_generate.py` | `:56`、`:86` |
| `miles_portal/tenant/models/services/usage.py` | `:128`、`:167` |
| `miles_portal/tenant/agents/services/agent/chat_rag.py` | `:382` |
| `miles_portal/tenant/attachments/services/media_reader.py` | `:44`、`:50` |
| `miles_portal/tenant/tools/services/flow_invoker.py` | `:40` |
| `miles_portal/tenant/flows/services/run_context.py` | `:25` |
| `miles_portal/tenant/flows/services/subflow_loader.py` | `:25` |
| `miles_portal/tenant/prompts/services/template_loader.py` | `:42` |
| `miles_portal/tenant/compliance/services/scan_words_loader.py` | `:24` |

同时更新这些文件里**只描述旧机制**的注释/docstring（例如
`rag_nodes.py:15` 的「KnowledgeSearch 节点内 ``short_db_session`` 独立开库」、
`media_reader.py:27` 的「每调用新开 ``short_db_session``」、`media_reader.py:71` 的
「与 ``FlowMediaReader``（自开 ``short_db_session``）互补」、
`chat_rag.py:380` 的「短会话走 short_db_session」）：改述为「每调用新开会话，与调用方
事务无关」，**保留**其「独立于调用方事务」的原意，不要顺手改行为。

- [ ] **Step 2b: 回退 4 处 `get_worker_session` 调用点（Task 2 方案 B 顺延的部分）**

`get_worker_session` 在 Task 1 之后已是 `async with AsyncSessionLocal()` 的纯转发，故与上一步
等价；这一步只是把最后 4 处调用点也收回来，使 Step 3 能删壳。

| 模块 | 站点 |
|---|---|
| `miles_worker/tasks/agent_schedule.py` | `:33` |
| `miles_worker/tasks/model_health.py` | `:27` |
| `miles_portal/tenant/generative/services/job_execution.py` | `:122`、`:192` |

`job_execution.py` 两处站点上方各有一行注释：

```python
# Celery fork 后父进程的全局 engine 不可复用；用 get_worker_session 创建全新的 engine
```

**这行注释现在是错的，必须一并改掉**：engine 自 Task 1 起按**事件循环**持有，与「fork」无关，
`get_worker_session()` 也不再「创建全新的 engine」（它只是转发）。改述为「engine 按事件循环
持有，直接取 `AsyncSessionLocal()` 即与当前 loop 对齐」，不要保留 fork 措辞。

- [ ] **Step 3: 删除两个已无人使用的转发壳**

> 顺序要求：必须在 Step 2 把 18 处调用点全部改完之后再删，否则中间态编译不过。

`async_session.py`：删掉 `get_worker_session` 与 `short_db_session`，以及只被它们使用的
import（`AsyncIterator`、`asynccontextmanager`；`get_db` 不用这两个）。同时把模块 docstring
里任何「回退全局」的表述去掉。

删除后 `async_session.py` 应只剩：模块 docstring、imports、`settings`、`build_engine`、
`_loop_engines`、`_loop_engine_and_maker`、`get_engine`、`AsyncSessionLocal`、
`dispose_loop_engines`、`run_worker_db_coro`、`get_db`。
（`_worker_sessionmaker` 三个符号在 Task 1 已删，此处不应再有它们。）

`__init__.py`：import 块与 `__all__` 去掉 `get_worker_session` 与 `short_db_session`。

- [ ] **Step 4: 解散旧护栏、撤掉 `_Boom` 机件**

删除这份文件（Task 1 已删掉另外两份以旧机制为主题的）：
```bash
git rm tests/infra/test_no_global_session_in_worker_paths.py
```

在下列文件中撤掉 `_Boom` 类与「patch `short_db_session` + patch `AsyncSessionLocal`(raising=False)」
的机件，把这些用例回退为**普通脚手架**：按模块属性打桩 `AsyncSessionLocal` 注入假会话，
断言原本的业务结果（这些断言本身要**保留**，只换打桩目标）：

| 测试文件 | 说明 |
|---|---|
| `tests/flow/test_generative_nodes.py` | 生图/生视频节点 |
| `tests/flow/test_prompt_template_node.py` | `rag_nodes` |
| `tests/rag/test_rag_qa_nodes_share_generate.py` | LangGraph `retrieve` 节点 |
| `tests/tenant/models/test_flow_usage_sink.py` | `FlowUsageSink.record` |
| `tests/tenant/models/test_chat_usage_sink_session.py` | `ChatUsageSink.record` |
| `tests/tenant/models/test_chat_usage_accumulation.py` | 用量累计 |
| `tests/tenant/models/_usage_doubles.py` | 共享替身模块 |
| `tests/tenant/flows/test_subflow_loader.py` | 子流程图加载 |
| `tests/tenant/flows/test_run_context_session.py` | 模型解析 |
| `tests/tenant/prompts/test_template_loader.py` | 提示词模板加载 |
| `tests/tenant/compliance/test_scan_words_loader.py` | 敏感词加载 |
| `tests/tenant/tools/test_flow_invoker_session.py` | 平台工具调用 |
| `tests/tenant/generative/test_progress_session.py` | 生成任务进度/取消 |
| `tests/tenant/attachments/test_flow_media_reader.py` | 媒体读取器 |
| `tests/tenant/agents/test_rag_usage_accumulation.py` | RAG 用量累计 |
| `tests/tenant/agents/test_chat_rag_connection_release.py` | 线性检索/直连对话 |
| `tests/tenant/agents/test_job_watch.py` | 现有 `AsyncSessionLocal` 打桩，通常无需改 |
| `tests/tenant/agents/test_agent_chat_ws.py` | 同上 |

**另有 3 处与 `get_worker_session` 有关的测试机件**（Task 2 方案 B 的顺延物）：

- `tests/tenant/generative/test_job_execution_runner.py:107` 用
  `monkeypatch.setattr(job_execution, "get_worker_session", ...)` 注入假会话——打桩目标改成
  `AsyncSessionLocal`（`job_execution` 模块级不再有 `get_worker_session` 这个名字，不改会
  `AttributeError`）。
- `tests/tenant/flows/test_run_context_session.py:4` 与
  `tests/tenant/tools/test_flow_invoker_session.py:3` 的 docstring 用「在
  ``get_worker_session()`` 子树内可达」描述可达性——改述为语义描述（「在 Worker 任务子树内
  可达」），**断言不动**。

**注意**：`test_chat_rag_connection_release.py` 与 `test_flow_media_reader.py` 里有用例
断言「检索短会话在 commit 之前已退出」之类的**连接释放时序**——那属于前一个专项的
不变量，**不要删**，只把打桩目标从 `short_db_session` 换成 `AsyncSessionLocal`。

**这三类文件已在 Task 1 处理过，本步不要重复动**：`test_short_db_session.py`、
`test_worker_session_composition.py`（已删）、`test_db_pool_settings.py`（已改）。

- [ ] **Step 5: 全仓确认已清零**

Run:
```bash
rg -n "short_db_session|get_worker_session" --type py packages/ tests/ docs/guides docs/features docs/architecture
```
Expected: **零命中**（`docs/superpowers/` 的历史 spec/plan 除外，那些是历史记录，不动）。
今日已知会在 Step 2/2b/4 改掉的命中：`packages/` 下 22 处调用点 + 3 个测试文件
（`test_job_execution_runner.py:107`、`test_run_context_session.py:4`、
`test_flow_invoker_session.py:3`）。

> 若 `docs/` 下的现役文档有命中，一并改述（参照上一分支的做法：把机制名词替换为
> 「每调用新开会话」的语义描述）。历史 spec/plan 保持原样。

- [ ] **Step 6: 跑测试与门禁**

Run:
```bash
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿，**测试数比 Task 2 结束时减少**（删掉 `test_no_global_session_in_worker_paths.py`、
撤掉部分 `_Boom` 机件），**不得出现 warning 增多**。具体数量以实测为准，逐条确认失败都来自
「已删符号」而非行为回归。

本 Task 的 BASE 计数是 **1096**（Task 2 收口后），护栏文件现有 **19** 条用例 ⇒ 预期
**1077**（撤机件只换打桩目标，不增删用例）。

> ⚠️ 必须用 `python -m pytest`，**不要**用 console script `pytest`：后者不会把 CWD 注入
> `sys.path`，`tests/` 又不是包，会以 `ModuleNotFoundError: No module named 'tests'` 在收集期
> 炸掉 9 个模块——那是调用方式问题，不是代码回归。

Run（其余四条）:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check
```
Expected: 全部通过。

- [ ] **Step 7: Commit**

```bash
git add -A packages/ tests/ docs/
git commit -F - <<'EOF'
refactor(db): 退役会话转发壳，调用点回归统一工厂

Task 1 已让 AsyncSessionLocal 自身 loop 感知，get_worker_session / short_db_session
随之塌缩为「async with AsyncSessionLocal()」的纯转发——这层间接已不携带任何信息。
本步把 16 个模块 22 处调用点（18 处 short_db_session + 4 处 get_worker_session）改回直接用
AsyncSessionLocal()，并删掉两个壳，使「会话从哪来」在全仓只有一个答案。

同时解散只服务于旧机制的结构不变量清单与 13 个测试文件里的「调用即炸」打桩机件：
它们守护的概念（按站点选工厂）已不存在。各用例原有的业务断言保留，只把打桩目标
换回 AsyncSessionLocal；连接释放时序类断言（前一专项引入）不动。

无行为变更：转发壳与 AsyncSessionLocal() 在 Task 1 之后即等价。
EOF
```

---

### Task 4: 终检

**Files:**
- Modify: `docs/superpowers/specs/2026-09-15-loop-aware-db-engine-design.md`（§10 修订记录）
- 不改任何代码（除非验证发现问题）

**Interfaces:**
- Consumes：前三 Task 的全部交付物
- Produces：无

- [ ] **Step 1: 真库端到端复跑（含敏感性对照）**

写一个**不提交**的探针到 `/tmp`：连续 6 次 `run_worker_db_coro(...)`，每次在协程内跑一个
真实的 DB 站点（至少包含 `progress.update_generative_job_progress` 与
`rag_qa.retrieve`），断言 **6/6 成功**。

必须带**敏感性对照**：另一组把注册表绕过、固定复用同一个 engine（等价旧行为），
应出现约半数失败并报 `got Future attached to a different loop`。没有这个对照，
「6/6 成功」可能只是因为探针根本没触到跨 loop 路径。

同时实测**连接泄漏**：6 次任务后查 `pg_stat_activity`（或等价计数），确认连接数不随
任务数线性增长。把两组输出与连接数一并写进报告。

- [ ] **Step 2: 五条门禁**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿，warning 恰为 2（既有）。

- [ ] **Step 3: 确认非目标未被误改**

Run:
```bash
git diff main...HEAD --stat
```
逐项核对：**不得**出现 `miles_core/infra/redis/`、`FlowMediaReader`/`SessionMediaReader`
的语义改动、tool agent / a2a 路径改动、`get_db()` 形状改动。

Run:
```bash
rg -n "from miles_core.infra.redis" packages/miles-core/src/miles_core/infra/db/
```
Expected: 零命中（DB 层不得依赖 Redis，spec §4）。

- [ ] **Step 4: 更新 spec 修订记录**

在 `docs/superpowers/specs/2026-09-15-loop-aware-db-engine-design.md` 的
`## 10. 修订记录` 追加一条（日期 2026-09-15），如实记录：已实施、最终测试数、
端到端探针结果（含对照组与连接数）、以及实施中与设计不符之处。**必须包含**这条修正：

> 第 5 节原称「`WeakKeyDictionary` 的弱键让 loop 回收即自动摘除」——实施后实测证明该说法
> 错误（asyncpg 连接强引用 loop、池强持有连接、注册表强引用 engine ⇒ 条目被钉住，只要有存活
> 连接就永不失效）。已改为「弱键只规避 `id(loop)` 复用，**唯一释放路径是显式
> `dispose_loop_engines()`**」，§5 与 §8 均已同步；代码 docstring 同。

若实现过程中还发现了 spec 未预见的情况，同时补进 §8 风险表。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-09-15-loop-aware-db-engine-design.md
git commit -F - <<'EOF'
docs(spec): 记录 loop 感知引擎的实施结果

补记实施后的测试数、真库端到端探针结果（含敏感性对照组与连接数观测），以及与
设计的偏差（若有）。
EOF
```

---

## 自检记录

**Spec 覆盖核对**

| spec 章节 | 对应 Task |
|---|---|
| §5.1 注册表（`_loop_engines` / `get_engine` / `AsyncSessionLocal` / `dispose_loop_engines`） | Task 1 Step 3 |
| §5.2 符号收敛（删 `engine`、`get_worker_session`、`short_db_session`、ContextVar 组） | Task 1 Step 3（`engine` + ContextVar 组 + 塌缩两个壳）+ Task 3 Step 3（删两个壳） |
| §5.2 `health_checks` 改 `get_engine()` | Task 1 Step 4 |
| §5.3 `run_worker_db_coro` + 3 个 Celery 入口 | Task 2 |
| §5.3 Redis 不进该 helper | Task 2 Step 3/4、Task 4 Step 3 |
| §5.3 CLI 脚本不改 | Task 3 未列入（正确） |
| §6.1 18 处调用点回退 | Task 3 Step 2 |
| §6.2 5 个既有站点自动变安全（无需改动） | Task 3 Step 7 提交信息说明；Task 4 无改动 |
| §7 新不变量测试（跨 loop 不复用 / dispose 幂等 / 边界时序 / 真库端到端） | Task 1 Step 1、Task 2 Step 1、Task 4 Step 1 |
| §7 旧护栏解散（三份文件） | Task 1 Step 5(b)（两份以旧机制为主题）+ Task 3 Step 4（结构不变量清单） |
| §7 门禁 | 每个 Task 的末步 |
| §8 风险（连接泄漏实测） | Task 4 Step 1 |
| §9 遗留（Redis id 复用、tool agent 等） | 明示不做；Task 4 Step 3 核对未误改 |

**Pre-flight 冲突及其裁决**：原计划让 Task 1 把旧机制**逐字保留**，会留下两条 engine 创建路径与
一处引用已删符号的陈旧 docstring（评审者会正当拦下）。经裁决改为**在 Task 1 就地塌缩为纯转发**，
并把两份以旧机制为主题的测试文件在 Task 1 删除、把池参数接线断言接到新机制上。本计划文本已按此
裁决改写，无需执行者再裁决。

**占位符扫描**：无 TBD/TODO。所有代码步骤均给出完整可粘贴代码；测试断言均绑定
「身份/时序/业务结果」而非「没抛异常」。`test_distinct_loops_get_distinct_engines` 与
`test_same_loop_reuses_one_engine` 都以 `len(built)` 钉住构造次数，避免「没建 engine 也能过」。

**类型一致性**：`get_engine() -> AsyncEngine`、`AsyncSessionLocal() -> AsyncSession`、
`dispose_loop_engines() -> None`（async）、`run_worker_db_coro(coro) -> Any` 在 Task 1/2/3/4
中拼写一致；`_loop_engine_and_maker()` 仅 Task 1 内部使用。

**开放风险**：spec §8 列出的「`WeakKeyDictionary` 以 loop 为键」已被实测确认（标准
asyncio loop 可弱引用，仓库未用 uvloop）。`import asyncio` 一律置于模块顶层，无对冲写法。

**测试数口径**：基线 1090（已实测确认）→ Task 1 后 **1090**（+7 −2 −4 −2 = 1089，修复轮
把一条近恒真用例拆成两条 +1）→ Task 2 后预期 **1094**（+4）→ Task 3 后以实测为准（只减不增）。
若实测与预期不符，先查清差额来源，**不要直接改期望值**。
