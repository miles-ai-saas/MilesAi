"""Celery Worker/Beat 启动模块：在最小 app 上补齐任务注册、队列路由与调度。

任务名见 app.core.jobs.tasks.TASK_NAMES。启动示例：
  celery -A app.workers.app worker -Q parse,default
"""

from app.core.config import get_settings
from app.core.jobs.celery_app import celery_app
from app.core.jobs.tasks import TASK_NAMES
from app.core.logging import setup_logging

setup_logging()
settings = get_settings()

celery_app.conf.update(
    include=["app.workers.tasks"],
    task_annotations={
        TASK_NAMES["ingest_document"]: {
            "soft_time_limit": settings.celery_ingest_soft_time_limit_sec,
            "time_limit": settings.celery_ingest_time_limit_sec,
        },
        TASK_NAMES["run_generative_video_job"]: {
            "soft_time_limit": settings.celery_generative_soft_time_limit_sec,
            "time_limit": settings.celery_generative_time_limit_sec,
        },
        TASK_NAMES["run_generative_image_job"]: {
            "soft_time_limit": settings.celery_generative_soft_time_limit_sec,
            "time_limit": settings.celery_generative_time_limit_sec,
        },
    },
    beat_schedule={
        "tick-agent-schedules": {"task": TASK_NAMES["tick_agent_schedules"], "schedule": 60.0},
        "probe-models-health": {"task": TASK_NAMES["probe_models_health"], "schedule": 900.0},
    },
)

__all__ = ["celery_app"]
