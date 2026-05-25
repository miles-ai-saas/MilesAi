"""文档入库失败状态落库（须在 Celery 重试 rollback 前 commit）。

run_ingest 异常 → persist_document_ingest_failure（立即 commit）；
Celery max_retries 耗尽 → ensure_document_failure_if_still_processing 兜底 PENDING/PARSING/EMBEDDING。
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
    """写入失败状态并立即 commit，避免 get_sync_db 异常 rollback 吞掉状态。"""
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
    """Celery 重试耗尽后兜底：仍在排队/处理中的文档标记为失败。"""
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
