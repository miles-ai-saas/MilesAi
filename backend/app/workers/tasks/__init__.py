"""Celery 任务模块聚合（被 app.workers.app include 加载）。"""

from app.workers.tasks.health import ping
from app.workers.tasks.ingest import ingest_document

__all__ = ["ping", "ingest_document"]
