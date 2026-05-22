"""Celery Worker 侧同步更新任务记录。"""

from uuid import UUID

from sqlalchemy import select

from app.infra.db import get_sync_db
from app.models.task import CeleryTaskRecord, TaskStatus


def sync_task_by_celery_id(
    celery_task_id: str,
    status: TaskStatus,
    *,
    fail_reason: str | None = None,
) -> None:
    with get_sync_db() as db:
        record = db.scalar(
            select(CeleryTaskRecord).where(CeleryTaskRecord.celery_task_id == celery_task_id)
        )
        if not record:
            return
        record.status = status
        if fail_reason is not None:
            record.fail_reason = fail_reason[:2000] if fail_reason else None
        db.flush()


def sync_task_by_document(document_id: str, status: TaskStatus, *, fail_reason: str | None = None) -> None:
    with get_sync_db() as db:
        record = db.scalars(
            select(CeleryTaskRecord)
            .where(
                CeleryTaskRecord.resource_type == "document",
                CeleryTaskRecord.resource_id == UUID(document_id),
            )
            .order_by(CeleryTaskRecord.created_at.desc())
            .limit(1)
        ).first()
        if not record:
            return
        record.status = status
        if fail_reason is not None:
            record.fail_reason = fail_reason[:2000] if fail_reason else None
        db.flush()
