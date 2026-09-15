"""PostgreSQL 连接与会话。

FastAPI 依赖 get_db（异步）；Celery/ingest 使用 get_sync_db（同步）。
"""

from miles_core.infra.db.async_session import (
    AsyncSessionLocal,
    dispose_loop_engines,
    get_db,
    get_engine,
    run_worker_db_coro,
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
    "run_worker_db_coro",
    "sync_engine",
]
