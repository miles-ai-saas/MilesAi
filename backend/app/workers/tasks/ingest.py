from app.workers.app import celery_app
from app.models.task import TaskStatus
from app.app_tenant.kb.services.ingest import run_ingest
from app.app_tenant.tasks.services.sync import sync_task_by_celery_id


@celery_app.task(name="app.workers.tasks.ingest.ingest_document", bind=True, max_retries=3)
def ingest_document(self, document_id: str) -> str:
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        run_ingest(document_id)
        sync_task_by_celery_id(self.request.id, TaskStatus.SUCCESS)
        return "ok"
    except Exception as exc:
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc
