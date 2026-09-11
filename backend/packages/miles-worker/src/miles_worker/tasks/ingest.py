"""
Celery 知识库文档入库任务。

队列
----
通常走 ``embed`` 或 ``default`` 队列（见 Worker 启动参数）。

与租户任务表
------------
``sync_task_by_celery_id`` 同步 ``tenant_tasks`` 状态，供工作台「任务」页展示。

重试
----
``max_retries=3``，间隔 ``INGEST_RETRY_COUNTDOWN_SEC``；
耗尽后 ``ensure_document_failure_if_still_processing`` 将仍卡在
PENDING/PARSING/EMBEDDING 的文档标为 EMBED_FAILED。
"""

from miles_worker.app import celery_app
from miles_core.models.task.task_record import TaskStatus
from miles_portal.tenant.kb.services.ingest import run_ingest
from miles_portal.tenant.kb.services.ingest_failure import ensure_document_failure_if_still_processing
from miles_portal.tenant.tasks.services.sync import sync_task_by_celery_id

# 与 max_retries=3 配合：最多 4 次执行（首次 + 3 次重试）
INGEST_RETRY_COUNTDOWN_SEC = 30


@celery_app.task(name="miles_worker.tasks.ingest.ingest_document", bind=True, max_retries=3)
def ingest_document(self, document_id: str) -> str:
    """
    异步执行单文档入库。

    参数 document_id 为 PG ``documents.id`` 字符串形式。
    成功返回 ``"ok"``；失败触发 Celery retry 或最终抛出让 broker 标记失败。
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
