"""Worker 健康检查任务。"""

from miles_core.jobs.tasks import TASK_NAMES
from miles_worker.app import celery_app


@celery_app.task(name=TASK_NAMES["ping"])
def ping() -> str:
    """用于验证 Celery broker/worker 是否连通。"""
    return "pong"
