"""Celery 知识库文档入库任务（队列 embed / default）。"""

from app.workers.app import celery_app
from app.models.task import TaskStatus
from app.tenant.kb.services.ingest import run_ingest
from app.tenant.kb.services.ingest_failure import ensure_document_failure_if_still_processing
from app.tenant.tasks.services.sync import sync_task_by_celery_id

INGEST_RETRY_COUNTDOWN_SEC = 30


@celery_app.task(name="app.workers.tasks.ingest.ingest_document", bind=True, max_retries=3)
def ingest_document(self, document_id: str) -> str:
    """委托 tenant.kb.ingest.run_ingest，与 API 上传解耦。"""
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        run_ingest(document_id)
        sync_task_by_celery_id(self.request.id, TaskStatus.SUCCESS)
        return "ok"
    except Exception as exc:
        reason = str(exc)[:2000]
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=reason)
        if self.request.retries >= self.max_retries:
            ensure_document_failure_if_still_processing(document_id, reason=reason)
            raise
        raise self.retry(exc=exc, countdown=INGEST_RETRY_COUNTDOWN_SEC) from exc
