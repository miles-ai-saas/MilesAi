"""Celery 任务模块聚合（被 app.workers.app include 加载）。"""

from app.workers.tasks.health import ping
from app.workers.tasks.ingest import ingest_document
from app.workers.tasks.agent_schedule import run_agent_schedule, tick_agent_schedules
from app.workers.tasks.generative import run_generative_image_job, run_generative_video_job

__all__ = [
    "ping",
    "ingest_document",
    "run_agent_schedule",
    "tick_agent_schedules",
    "run_generative_video_job",
    "run_generative_image_job",
]
