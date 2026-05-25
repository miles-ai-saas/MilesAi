"""Celery 知识库文档入库任务（队列 embed / default）。

链路：API upload_document → ingest_document.delay
     → run_ingest（状态机）→ run_ingest_pipeline（解析/分片/向量）
     → embed_texts_for_kb_sync → upsert_chunk_vector → Milvus/pgvector。
失败：run_ingest 内 persist_document_ingest_failure（先 commit）；
     重试耗尽后 ensure_document_failure_if_still_processing 兜底。
"""

from app.workers.app import celery_app
from app.models.task import TaskStatus
from app.tenant.kb.services.ingest import run_ingest
from app.tenant.kb.services.ingest_failure import ensure_document_failure_if_still_processing
from app.tenant.tasks.services.sync import sync_task_by_celery_id

# Celery 重试间隔（秒）；与 max_retries=3 配合，共最多 4 次执行
INGEST_RETRY_COUNTDOWN_SEC = 30


@celery_app.task(name="app.workers.tasks.ingest.ingest_document", bind=True, max_retries=3)
def ingest_document(self, document_id: str) -> str:
    """异步执行单文档入库，并同步租户任务表状态。

    成功：TaskStatus.SUCCESS；失败：FAILED + 未耗尽重试时 countdown 重试；
    耗尽重试且文档仍在 PENDING/PARSING/EMBEDDING 时标记 EMBED_FAILED。
    """
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
