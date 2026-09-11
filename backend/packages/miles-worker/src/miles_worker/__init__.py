"""Celery 包入口：导出 celery_app 供 FastAPI 与 CLI 引用。"""

from miles_worker.app import celery_app

__all__ = ["celery_app"]
