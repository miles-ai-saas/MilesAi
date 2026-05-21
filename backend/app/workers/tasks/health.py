from app.workers.app import celery_app


@celery_app.task(name="app.workers.tasks.health.ping")
def ping() -> str:
    return "pong"
