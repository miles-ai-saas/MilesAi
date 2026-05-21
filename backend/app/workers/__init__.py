"""Celery 异步任务。"""

from app.workers.app import celery_app

__all__ = ["celery_app"]
