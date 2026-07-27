"""异步 PostgreSQL 引擎与会话（FastAPI 主路径）。"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Celery ``asyncio.run`` 任务内绑定的 sessionmaker（与当前 loop 同寿），
# 供进度/取消检测开独立短会话，避免复用全局 AsyncSessionLocal。
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

    Fork 后父进程的全局 engine 内部 asyncpg 连接残留了旧事件循环的 Future，
    任何 dispose/close 操作都会触发 ``got Future attached to a different loop``。
    本函数创建全新的 engine + session，并在任务生命周期内绑定 sessionmaker，
    供 ``generative_job_db_session`` 开独立短会话。

    用法::

        async with get_worker_session() as db:
            ...
            await db.commit()
    """
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )
    _maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    token = _set_worker_sessionmaker(_maker)
    try:
        async with _maker() as session:
            yield session
    finally:
        _reset_worker_sessionmaker(token)
        await _engine.dispose()


@asynccontextmanager
async def generative_job_db_session() -> AsyncIterator[AsyncSession]:
    """进度/取消检测用会话。

    - Worker：在当前任务的 worker engine 上开独立短会话（同 loop、不共享主事务）
    - API：回退到全局 ``AsyncSessionLocal``
    """
    maker = _worker_sessionmaker.get()
    if maker is not None:
        async with maker() as session:
            yield session
        return
    async with AsyncSessionLocal() as session:
        yield session
