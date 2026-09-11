"""Celery 任务记录：与文档 ingest 等异步作业状态同步。

API 上传时 create_record；Worker 内 sync_task_by_celery_id 更新状态；
get_task 可对照 Celery AsyncResult 纠偏。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.jobs.celery_app import celery_app
from miles_core.jobs.tasks import INGEST_DOCUMENT
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_core.models.task.task_record import CeleryTaskRecord, TaskStatus
from miles_common.schema import PageParams, PageResult
from miles_portal.tenant.tasks.meta import tasks_meta_dict
from miles_portal.tenant.tasks.schemas.meta import TaskMetaOut
from miles_portal.tenant.tasks.schemas.task import TaskBatchCancelResult, TaskRecordOut
from miles_core.logging import get_logger
from miles_core.service import BaseService

logger = get_logger(__name__)


class TaskService(BaseService):
    """租户可见的 Celery 任务记录 CRUD 与重试/取消。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> TaskMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return TaskMetaOut.model_validate(tasks_meta_dict())

    async def create_record(
        self,
        *,
        celery_task_id: str,
        task_name: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> CeleryTaskRecord:
        """投递 Celery 后写入 PENDING 记录（如 upload_document）。"""
        record = CeleryTaskRecord(
            tenant_id=self.ctx.tenant_id,
            celery_task_id=celery_task_id,
            task_name=task_name,
            status=TaskStatus.PENDING,
            resource_type=resource_type,
            resource_id=resource_id,
            created_by=self.ctx.user_id,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def _get_record_or_raise(self, task_id: str) -> CeleryTaskRecord:
        """支持 UUID 主键或 celery_task_id 查询。"""
        record = None
        try:
            record = await self.db.get(CeleryTaskRecord, UUID(task_id))
        except ValueError:
            pass
        if not record:
            record = await self.db.scalar(select(CeleryTaskRecord).where(CeleryTaskRecord.celery_task_id == task_id))
        if not record:
            raise NotFoundError("任务不存在")
        assert_tenant_access(self.ctx, record.tenant_id)
        return record

    async def list_tasks(
        self,
        params: PageParams,
        *,
        status: TaskStatus | None = None,
    ) -> PageResult[TaskRecordOut]:
        """分页列出当前租户异步任务。"""
        filters = list(tenant_filters(self.ctx, CeleryTaskRecord.tenant_id))
        if status:
            filters.append(CeleryTaskRecord.status == status)
        count_stmt = select(func.count(CeleryTaskRecord.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = select(CeleryTaskRecord).where(*filters).order_by(CeleryTaskRecord.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        rows = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[TaskRecordOut.model_validate(r) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def get_task(self, task_id: str) -> TaskRecordOut:
        """查询任务详情，必要时用 Celery 状态纠偏 DB。"""
        record = await self._get_record_or_raise(task_id)
        out = TaskRecordOut.model_validate(record)
        try:
            from celery.result import AsyncResult

            ar = AsyncResult(record.celery_task_id, app=celery_app)
            if ar.state and record.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                state_map = {
                    "PENDING": TaskStatus.PENDING,
                    "STARTED": TaskStatus.RUNNING,
                    "SUCCESS": TaskStatus.SUCCESS,
                    "FAILURE": TaskStatus.FAILED,
                    "REVOKED": TaskStatus.CANCELLED,
                }
                mapped = state_map.get(ar.state)
                if mapped and mapped != record.status:
                    record.status = mapped
                    if ar.failed() and ar.result:
                        record.fail_reason = str(ar.result)[:2000]
                    await self.db.flush()
                    out = TaskRecordOut.model_validate(record)
        except Exception:
            logger.warning(
                "Celery 状态纠偏失败 task_id=%s celery_task_id=%s",
                task_id,
                record.celery_task_id,
                exc_info=True,
            )
        return out

    async def cancel_task(self, task_id: str) -> TaskRecordOut:
        """revoke Celery 任务并标记 CANCELLED。"""
        record = await self._get_record_or_raise(task_id)
        if record.status in (TaskStatus.SUCCESS, TaskStatus.CANCELLED):
            raise BadRequestError("任务已结束，无法取消")
        celery_app.control.revoke(record.celery_task_id, terminate=True)
        record.status = TaskStatus.CANCELLED
        await self.db.flush()
        return TaskRecordOut.model_validate(record)

    async def batch_cancel_tasks(self, task_ids: list[str]) -> TaskBatchCancelResult:
        """批量取消；单条失败不中断，已结束任务记入 skipped。"""
        cancelled: list[TaskRecordOut] = []
        skipped: list[str] = []
        for task_id in task_ids:
            try:
                record = await self._get_record_or_raise(task_id)
            except NotFoundError:
                skipped.append(task_id)
                continue
            if record.status in (TaskStatus.SUCCESS, TaskStatus.CANCELLED):
                skipped.append(task_id)
                continue
            celery_app.control.revoke(record.celery_task_id, terminate=True)
            record.status = TaskStatus.CANCELLED
            cancelled.append(TaskRecordOut.model_validate(record))
        if cancelled:
            await self.db.flush()
        return TaskBatchCancelResult(cancelled=cancelled, skipped=skipped)

    async def retry_task(self, task_id: str) -> TaskRecordOut:
        """仅 document 类型：重新 delay ingest 并更新文档 PENDING。"""
        record = await self._get_record_or_raise(task_id)
        if record.resource_type != "document" or not record.resource_id:
            raise BadRequestError("仅支持文档入库任务重试")
        if record.status == TaskStatus.RUNNING:
            raise BadRequestError("任务运行中，请稍后再试")

        from miles_core.models.kb import Document, DocumentStatus

        from miles_core.soft_delete import is_marked_deleted

        doc = await self.db.get(Document, record.resource_id)
        if not doc or is_marked_deleted(doc):
            raise NotFoundError("关联文档不存在")

        new_task = celery_app.send_task(INGEST_DOCUMENT, args=[str(doc.id)])
        record.celery_task_id = new_task.id
        record.status = TaskStatus.PENDING
        record.fail_reason = None
        doc.status = DocumentStatus.PENDING
        doc.celery_task_id = new_task.id
        doc.fail_reason = None
        await self.db.flush()
        return TaskRecordOut.model_validate(record)
