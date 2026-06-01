"""交付物 CRUD 服务。

交付物是项目产出的有形成果——文档、设计稿、视频等。
状态流：draft → submitted → accepted / rejected
可关联到附件表、媒体资产表、知识库文档。
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.deliverable import DeliverableRepository
from app.biz.schemas.deliverable import (
    BizDeliverableCreate,
    BizDeliverableOut,
    BizDeliverableUpdate,
)
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.biz import BizDeliverable


class DeliverableService(BaseService):
    """交付物管理——属于项目维度，可按项目查询全部交付成果。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = DeliverableRepository(db)

    async def list_by_project(self, project_id: UUID) -> list[BizDeliverableOut]:
        """按项目查询交付物列表（按提交时间降序）。"""
        rows = await self.repo.list_by_project(self.ctx.tenant_id, project_id)
        return [self._to_out(r) for r in rows]

    async def create(self, body: BizDeliverableCreate) -> BizDeliverableOut:
        """创建交付物，可关联工作包、附件或媒体资产。"""
        row = BizDeliverable(
            tenant_id=self.ctx.tenant_id,
            project_id=body.project_id,
            work_package_id=body.work_package_id,
            name=body.name.strip(),
            type=body.type,
            attachment_id=body.attachment_id,
            media_asset_id=body.media_asset_id,
            version=body.version,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.deliverable.create",
            resource_type="biz_deliverable",
            resource_id=row.id,
            detail={"project_id": str(row.project_id), "name": row.name},
        )
        return self._to_out(row)

    async def update(self, deliverable_id: UUID, body: BizDeliverableUpdate) -> BizDeliverableOut:
        """编辑交付物，可更新名称、类型、状态、关联资源等。"""
        row = await self._get_or_raise(deliverable_id)
        old_status = row.status
        for f in ("name", "type", "status", "work_package_id", "attachment_id", "media_asset_id", "version"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f == "name" else val)
        await self.db.flush()
        await self.db.refresh(row)
        if body.status is not None and body.status != old_status:
            await log_biz_action(
                self.db, self.ctx,
                action="biz.deliverable.status_change",
                resource_type="biz_deliverable",
                resource_id=row.id,
                detail={"from": old_status, "to": body.status, "project_id": str(row.project_id)},
            )
        return self._to_out(row)

    async def delete(self, deliverable_id: UUID) -> None:
        """软删除交付物（仅标记 deleted_at）。"""
        row = await self._get_or_raise(deliverable_id)
        await mark_deleted(self.db, row)

    async def submit(self, deliverable_id: UUID) -> BizDeliverableOut:
        """提交交付物：draft/rejected → submitted。"""
        row = await self._get_or_raise(deliverable_id)
        if row.status not in ("draft", "rejected"):
            raise BadRequestError("仅草稿或已驳回状态可提交")
        row.status = "submitted"
        row.submitted_at = _now_iso()
        await self.db.flush()
        await self.db.refresh(row)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.deliverable.submit",
            resource_type="biz_deliverable",
            resource_id=row.id,
            detail={"project_id": str(row.project_id), "name": row.name},
        )
        return self._to_out(row)

    async def accept(self, deliverable_id: UUID) -> BizDeliverableOut:
        """验收通过：submitted → accepted。"""
        row = await self._get_or_raise(deliverable_id)
        if row.status != "submitted":
            raise BadRequestError("仅已提交状态可验收")
        row.status = "accepted"
        row.accepted_at = _now_iso()
        await self.db.flush()
        await self.db.refresh(row)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.deliverable.accept",
            resource_type="biz_deliverable",
            resource_id=row.id,
            detail={"project_id": str(row.project_id), "name": row.name},
        )
        return self._to_out(row)

    async def reject(self, deliverable_id: UUID) -> BizDeliverableOut:
        """驳回交付物：submitted → rejected。"""
        row = await self._get_or_raise(deliverable_id)
        if row.status != "submitted":
            raise BadRequestError("仅已提交状态可驳回")
        row.status = "rejected"
        row.accepted_at = None
        await self.db.flush()
        await self.db.refresh(row)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.deliverable.reject",
            resource_type="biz_deliverable",
            resource_id=row.id,
            detail={"project_id": str(row.project_id), "name": row.name},
        )
        return self._to_out(row)

    async def _get_or_raise(self, deliverable_id: UUID) -> BizDeliverable:
        row = await self.repo.get_by_id(deliverable_id)
        if not row:
            raise NotFoundError("交付物不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    def _to_out(self, row: BizDeliverable) -> BizDeliverableOut:
        return BizDeliverableOut(
            id=row.id, project_id=row.project_id, name=row.name,
            type=row.type, status=row.status,
            work_package_id=row.work_package_id,
            attachment_id=row.attachment_id,
            media_asset_id=row.media_asset_id,
            version=row.version,
            submitted_at=row.submitted_at, accepted_at=row.accepted_at,
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
