"""Worker 健康检查任务。"""

from miles_worker.app import celery_app


@celery_app.task(name="miles_worker.tasks.health.ping")
def ping() -> str:
    """用于验证 Celery broker/worker 是否连通。"""
    return "pong"
