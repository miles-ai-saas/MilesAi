"""Celery / 脚本使用的同步数据库会话。"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from miles_core.config import Settings, get_settings


def build_sync_engine(settings: Settings):
    """按 ``Settings`` 构造同步引擎（与 async ``build_engine`` 同源池参数）。"""
    return create_engine(
        settings.database_url_sync,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )


settings = get_settings()
sync_engine = build_sync_engine(settings)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """上下文管理器：成功 commit，异常 rollback 并 close。"""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
