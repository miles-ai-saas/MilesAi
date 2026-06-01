"""项目相关案例推荐（知识库入库交付物）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project_ai import BizRelatedCaseOut
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import not_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.biz import BizDeliverable, BizProject, BizWorkPackage
from app.models.biz.enums import ConfidentialityLevel
from app.models.kb import Document, KnowledgeBase


class ProjectRelatedCasesService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.project_repo = ProjectRepository(db)

    async def list_related_cases(self, project_id: UUID, *, limit: int = 8) -> list[BizRelatedCaseOut]:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, project.tenant_id)

        from app.biz.repositories.client import ClientRepository

        client = await ClientRepository(self.db).get_by_id(project.client_id)
        if client and client.confidentiality_level == ConfidentialityLevel.RESTRICTED.value:
            return []

        wps = await self.project_repo.get_work_packages(self.ctx.tenant_id, project_id)
        service_lines = {wp.service_line for wp in wps if wp.service_line}

        stmt = (
            select(
                BizDeliverable,
                BizProject.name.label("project_name"),
                BizProject.client_id,
                Document.filename.label("doc_title"),
                Document.kb_id,
                KnowledgeBase.name.label("kb_name"),
                BizWorkPackage.service_line,
            )
            .join(BizProject, BizProject.id == BizDeliverable.project_id)
            .join(Document, Document.id == BizDeliverable.kb_document_id)
            .join(KnowledgeBase, KnowledgeBase.id == Document.kb_id)
            .outerjoin(BizWorkPackage, BizWorkPackage.id == BizDeliverable.work_package_id)
            .where(
                BizDeliverable.tenant_id == self.ctx.tenant_id,
                not_deleted(BizDeliverable),
                not_deleted(BizProject),
                BizDeliverable.kb_document_id.is_not(None),
                BizDeliverable.status == "accepted",
                BizProject.id != project_id,
            )
            .order_by(BizProject.updated_at.desc())
            .limit(limit * 3)
        )
        rows = (await self.db.execute(stmt)).all()

        out: list[BizRelatedCaseOut] = []
        seen: set[str] = set()
        for r in rows:
            doc_id = str(r.BizDeliverable.kb_document_id)
            if doc_id in seen:
                continue
            same_client = r.client_id == project.client_id
            same_line = r.service_line in service_lines if r.service_line else False
            if not same_client and not same_line:
                continue
            seen.add(doc_id)
            out.append(BizRelatedCaseOut(
                kb_id=r.kb_id,
                kb_name=r.kb_name or "知识库",
                document_id=r.BizDeliverable.kb_document_id,
                document_title=r.doc_title or r.BizDeliverable.name,
                project_id=r.BizDeliverable.project_id,
                project_name=r.project_name or "—",
                service_line=r.service_line,
                deliverable_name=r.BizDeliverable.name,
            ))
            if len(out) >= limit:
                break
        return out
