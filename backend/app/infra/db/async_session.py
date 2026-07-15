"""异步 PostgreSQL 引擎与会话（FastAPI 主路径）。"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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
    本函数创建全新的 engine + session，彻底隔离。

    用法（替换 ``AsyncSessionLocal``）：::

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
    try:
        async with _maker() as session:
            yield session
    finally:
        await _engine.dispose()
