"""PostgreSQL 连接与会话。

FastAPI 依赖 get_db（异步）；Celery/ingest 使用 get_sync_db（同步）。
"""

from app.infra.db.async_session import AsyncSessionLocal, engine, get_db, get_worker_session
from app.infra.db.base import Base
from app.infra.db.sync import SyncSessionLocal, get_sync_db, sync_engine

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "SyncSessionLocal",
    "engine",
    "get_db",
    "get_sync_db",
    "get_worker_session",
    "sync_engine",
]
