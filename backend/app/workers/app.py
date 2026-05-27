"""Celery 应用：ingest 走 parse 队列，与 API 共享同一套 app 代码与配置。

任务注册：include=app.workers.tasks；路由见 task_routes（ingest→parse 队列）。
Worker 启动示例：celery -A app.workers.app worker -Q parse,default

与租户任务表：ingest_document 内 sync_task_by_celery_id 更新 CeleryTaskRecord。
"""

from celery import Celery

from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
settings = get_settings()

celery_app = Celery(
    "milesai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    # ingest_document 实际消费 parse/default；ocr/embed 队列预留扩展
    task_routes={
        "app.workers.tasks.ingest.*": {"queue": "parse"},
        "app.workers.tasks.ocr.*": {"queue": "ocr"},
        "app.workers.tasks.embed.*": {"queue": "embed"},
    },
    beat_schedule={
        "tick-agent-schedules": {
            "task": "app.workers.tasks.agent_schedule.tick_agent_schedules",
            "schedule": 60.0,
        },
        "probe-models-health": {
            "task": "app.workers.tasks.model_health.probe_models_health",
            "schedule": 900.0,
        },
    },
)
