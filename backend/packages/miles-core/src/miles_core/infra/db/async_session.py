"""异步 PostgreSQL 引擎与会话（FastAPI 主路径）。"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token

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


engine = build_engine(settings)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Celery ``asyncio.run`` 任务内绑定的 sessionmaker（与当前 loop 同寿），
# 供 ``short_db_session`` 开独立短会话，避免复用全局 AsyncSessionLocal。
_worker_sessionmaker: ContextVar[async_sessionmaker[AsyncSession] | None] = ContextVar(
    "milesai_worker_sessionmaker",
    default=None,
)


def _set_worker_sessionmaker(
    maker: async_sessionmaker[AsyncSession] | None,
) -> Token[async_sessionmaker[AsyncSession] | None]:
    return _worker_sessionmaker.set(maker)


def _reset_worker_sessionmaker(token: Token[async_sessionmaker[AsyncSession] | None]) -> None:
    _worker_sessionmaker.reset(token)


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

    Celery 任务入口每次 ``asyncio.run`` 都新建事件循环，而全局 ``engine`` 的连接池里可能
    仍留着上一个 loop 创建的 asyncpg 连接：新 loop 里**第一次**用全局会话复用该连接，即抛
    ``got Future attached to a different loop``。实测同一进程连续 6 次 ``asyncio.run``，
    第 2/4/6 次失败（约一半），与 fork 无关——fork 只是更早暴露这一现象。
    本函数按当前 loop 新建 engine + session，并在任务生命周期内绑定 sessionmaker，
    供 ``short_db_session`` 开独立短会话。

    用法::

        async with get_worker_session() as db:
            ...
            await db.commit()
    """
    # 必须走 build_engine：手搓 engine 会静默忽略 db_pool_size / db_max_overflow /
    # db_pool_timeout（当前值恰为 SQLAlchemy 默认，所以只在调参时才会暴露）。
    _engine = build_engine(settings)
    _maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    token = _set_worker_sessionmaker(_maker)
    try:
        async with _maker() as session:
            yield session
    finally:
        _reset_worker_sessionmaker(token)
        await _engine.dispose()


@asynccontextmanager
async def short_db_session() -> AsyncIterator[AsyncSession]:
    """开一个短独立会话（与调用方事务无关）。

    - Worker：在当前任务绑定的 engine 上开（Celery 每次 ``asyncio.run`` 都是新 loop，
      全局 engine 池里的连接属于上一个 loop，复用会抛
      ``got Future attached to a different loop``）。
    - API / 脚本：无 worker engine 绑定时回退全局 ``AsyncSessionLocal``。
    """
    maker = _worker_sessionmaker.get()
    if maker is not None:
        async with maker() as session:
            yield session
        return
    async with AsyncSessionLocal() as session:
        yield session
