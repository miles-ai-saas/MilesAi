"""Celery 任务模块聚合（被 miles_worker.app include 加载）。"""

from miles_worker.tasks.health import ping
from miles_worker.tasks.ingest import ingest_document
from miles_worker.tasks.agent_schedule import run_agent_schedule, tick_agent_schedules
from miles_worker.tasks.generative import run_generative_image_job, run_generative_video_job
from miles_worker.tasks.model_health import probe_models_health

__all__ = [
    "ping",
    "ingest_document",
    "run_agent_schedule",
    "tick_agent_schedules",
    "run_generative_video_job",
    "run_generative_image_job",
    "probe_models_health",
]
