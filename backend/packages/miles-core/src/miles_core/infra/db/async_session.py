"""异步 PostgreSQL 引擎与会话（FastAPI 主路径）。

引擎按**事件循环**持有：Celery 任务入口每次 ``asyncio.run`` 都新建 loop，若复用绑在
旧 loop 上的连接池，会抛 ``got Future attached to a different loop``。以 loop 对象为
键（``WeakKeyDictionary``，loop 回收即自动摘除）懒建 engine，使 ``AsyncSessionLocal()``
对调用方而言与 loop 无关。
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
_loop_engines: WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = WeakKeyDictionary()


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

    幂等：无条目或已释放时为空操作。释放后同一 loop 再取会话会在下次连接时惰性重建池。
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
