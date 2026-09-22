"""PostgreSQL 连接与会话。

FastAPI 依赖 get_db（异步）；Celery/ingest 使用 get_sync_db（同步）。
同步引擎延迟加载：仅 ``from miles_core.infra.db import get_db`` 时不导入 psycopg2/create_engine。
"""

from __future__ import annotations

from typing import Any

from miles_core.infra.db.async_session import (
    AsyncSessionLocal,
    dispose_loop_engines,
    get_db,
    get_engine,
    run_worker_db_coro,
)
from miles_core.infra.db.base import Base

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "SyncSessionLocal",
    "dispose_loop_engines",
    "get_db",
    "get_engine",
    "get_sync_db",
    "run_worker_db_coro",
    "sync_engine",
]

_SYNC_EXPORTS = frozenset({"SyncSessionLocal", "get_sync_db", "sync_engine"})


def __getattr__(name: str) -> Any:
    if name in _SYNC_EXPORTS:
        from miles_core.infra.db import sync as sync_mod

        if name == "get_sync_db":
            return sync_mod.get_sync_db
        if name == "sync_engine":
            return sync_mod.sync_engine
        return sync_mod.SyncSessionLocal
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
