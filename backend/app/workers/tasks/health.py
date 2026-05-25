"""Worker 健康检查任务。"""

from app.workers.app import celery_app


@celery_app.task(name="app.workers.tasks.health.ping")
def ping() -> str:
    """用于验证 Celery broker/worker 是否连通。"""
    return "pong"
