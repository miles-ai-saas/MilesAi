from celery import Celery

from app.core.config import get_settings

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
    task_routes={
        "app.workers.tasks.ingest.*": {"queue": "parse"},
        "app.workers.tasks.ocr.*": {"queue": "ocr"},
        "app.workers.tasks.embed.*": {"queue": "embed"},
    },
)
