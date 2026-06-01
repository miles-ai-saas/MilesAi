"""项目结项向导：检查清单 + 可选案例入库 + 结项。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.client import ClientRepository
from app.biz.repositories.deliverable import DeliverableRepository
from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project import (
    BizArchivableDeliverableOut,
    BizArchiveCaseRequest,
    BizClosePreviewOut,
    BizCloseWizardOut,
    BizCloseWizardRequest,
)
from app.biz.services.project import ProjectService
from app.biz.services.project_archive import ProjectArchiveService
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.service import BaseService
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.biz.enums import ConfidentialityLevel, ProjectStatus


class ProjectCloseService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.project_repo = ProjectRepository(db)
        self.client_repo = ClientRepository(db)
        self.deliverable_repo = DeliverableRepository(db)
        self.project_svc = ProjectService(db, ctx)
        self.archive_svc = ProjectArchiveService(db, ctx)

    async def get_close_preview(self, project_id: UUID) -> BizClosePreviewOut:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, project.tenant_id)

        client = await self.client_repo.get_by_id(project.client_id)
        confidentiality = client.confidentiality_level if client else "normal"

        deliverables = await self.deliverable_repo.list_by_project(self.ctx.tenant_id, project_id)
        pending = sum(1 for d in deliverables if d.status in ("draft", "rejected"))
        submitted = sum(1 for d in deliverables if d.status == "submitted")

        wps = await self.project_repo.get_work_packages(self.ctx.tenant_id, project_id)
        incomplete_wps = sum(1 for w in wps if w.status not in ("done", "cancelled"))

        archivable = [
            BizArchivableDeliverableOut(
                id=d.id,
                name=d.name,
                version=d.version,
                has_attachment=bool(d.attachment_id),
            )
            for d in deliverables
            if d.status == "accepted" and d.attachment_id and not d.kb_document_id
        ]

        can_archive = confidentiality != ConfidentialityLevel.RESTRICTED.value and len(archivable) > 0
        blocked_reason = None
        if confidentiality == ConfidentialityLevel.RESTRICTED.value:
            blocked_reason = "涉密客户项目禁止案例入库"
        elif not archivable:
            blocked_reason = "没有可入库的已验收交付物"

        return BizClosePreviewOut(
            project_id=project.id,
            project_name=project.name,
            status=project.status,
            client_confidentiality=confidentiality,
            pending_deliverables=pending,
            submitted_deliverables=submitted,
            incomplete_work_packages=incomplete_wps,
            archivable_deliverables=archivable,
            can_archive=can_archive,
            archive_blocked_reason=blocked_reason,
        )

    async def execute_close_wizard(self, project_id: UUID, body: BizCloseWizardRequest) -> BizCloseWizardOut:
        preview = await self.get_close_preview(project_id)
        if preview.status in (ProjectStatus.CLOSED.value, ProjectStatus.CANCELLED.value):
            raise BadRequestError("项目已结项或已取消")

        archived_count = 0
        document_ids: list[UUID] = []

        if not body.skip_archive and body.deliverable_ids:
            if not body.kb_id:
                raise BadRequestError("请选择目标知识库")
            if not body.confirm_desensitized:
                raise BadRequestError("请确认已完成脱敏后再入库")
            if preview.client_confidentiality == ConfidentialityLevel.RESTRICTED.value:
                raise BadRequestError("涉密客户项目禁止案例入库")

            allowed = {d.id for d in preview.archivable_deliverables}
            invalid = [str(i) for i in body.deliverable_ids if i not in allowed]
            if invalid:
                raise BadRequestError("所选交付物不可入库")

            result = await self.archive_svc.archive_case(
                project_id,
                BizArchiveCaseRequest(kb_id=body.kb_id, run_parse=body.run_parse),
                deliverable_ids=body.deliverable_ids,
            )
            archived_count = result.archived_count
            document_ids = result.document_ids

        closed = await self.project_svc.close_project(project_id)
        return BizCloseWizardOut(
            project_id=closed.id,
            status=closed.status,
            archived_count=archived_count,
            document_ids=document_ids,
        )
