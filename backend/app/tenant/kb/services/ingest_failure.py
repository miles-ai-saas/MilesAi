"""
文档入库失败状态落库。

背景
----
Celery 任务在 ``get_sync_db()`` 上下文内抛异常时会 rollback；
若仅 flush 失败状态而不 commit，前端会一直看到 PARSING/EMBEDDING 卡住。

两阶段保障
----------
1. ``persist_document_ingest_failure``：``run_ingest`` 捕获异常后立即 commit。
2. ``ensure_document_failure_if_still_processing``：Celery 重试耗尽后兜底仍处理中的文档。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.db import get_sync_db
from app.models.kb import Document, DocumentStatus


def persist_document_ingest_failure(
    db: Session,
    doc: Document,
    *,
    phase: DocumentStatus,
    exc: Exception,
) -> None:
    """
    按阶段写入 PARSE_FAILED 或 EMBED_FAILED，并 **立即 commit**。

    EMBEDDING 阶段失败标 EMBED_FAILED，其余（含 PARSING）标 PARSE_FAILED。
    """
    doc.status = (
        DocumentStatus.EMBED_FAILED
        if phase == DocumentStatus.EMBEDDING
        else DocumentStatus.PARSE_FAILED
    )
    doc.fail_reason = str(exc)[:2000]
    db.flush()
    db.commit()


def ensure_document_failure_if_still_processing(
    document_id: str,
    *,
    reason: str,
) -> None:
    """
    Celery ``max_retries`` 用尽后的兜底。

    若文档仍处于 PENDING/PARSING/EMBEDDING，强制标为 EMBED_FAILED 并写入 fail_reason。
    """
    with get_sync_db() as db:
        doc = db.get(Document, UUID(document_id))
        if not doc or doc.deleted_at is not None:
            return
        if doc.status not in (
            DocumentStatus.PENDING,
            DocumentStatus.PARSING,
            DocumentStatus.EMBEDDING,
        ):
            return
        doc.status = DocumentStatus.EMBED_FAILED
        doc.fail_reason = reason[:2000]
        db.flush()
        db.commit()
