"""Celery / 脚本使用的同步数据库会话。

引擎与 sessionmaker 延迟初始化：纯异步进程 ``import miles_core.infra.db`` 时
不立刻 ``create_engine`` / 连接池，直至首次 ``get_sync_db`` / 访问 ``sync_engine``。
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from miles_core.config import Settings, get_settings

_sync_engine: Engine | None = None
_SyncSessionLocal: Any = None


def build_sync_engine(settings: Settings) -> Engine:
    """按 ``Settings`` 构造同步引擎（与 async ``build_engine`` 同源池参数）。"""
    return create_engine(
        settings.database_url_sync,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )


def _ensure_sync() -> tuple[Engine, Any]:
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None or _SyncSessionLocal is None:
        _sync_engine = build_sync_engine(get_settings())
        _SyncSessionLocal = sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False)
    return _sync_engine, _SyncSessionLocal


def __getattr__(name: str) -> Any:
    """兼容 ``from miles_core.infra.db.sync import sync_engine``。"""
    if name == "sync_engine":
        return _ensure_sync()[0]
    if name == "SyncSessionLocal":
        return _ensure_sync()[1]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """上下文管理器：成功 commit，异常 rollback 并 close。"""
    _, factory = _ensure_sync()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
