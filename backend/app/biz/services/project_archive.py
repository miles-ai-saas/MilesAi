"""项目结项案例沉淀至知识库。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.client import ClientRepository
from app.biz.repositories.deliverable import DeliverableRepository
from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project import BizArchiveCaseOut, BizArchiveCaseRequest
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.infra.storage import build_object_key
from app.infra.storage.resolve import resolve_object_storage_async
from app.models.biz.enums import ConfidentialityLevel, ProjectStatus
from app.models.kb import DocumentStatus
from app.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_allowed_hint
from app.tenant.attachments.repositories.attachment import AttachmentRepository
from app.tenant.kb.repositories.kb import DocumentRepository, KnowledgeBaseRepository
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes


class ProjectArchiveService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.project_repo = ProjectRepository(db)
        self.client_repo = ClientRepository(db)
        self.deliverable_repo = DeliverableRepository(db)
        self.att_repo = AttachmentRepository(db)

    async def archive_case(self, project_id: UUID, body: BizArchiveCaseRequest, *, deliverable_ids: list[UUID] | None = None) -> BizArchiveCaseOut:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, project.tenant_id)

        client = await self.client_repo.get_by_id(project.client_id)
        if not client:
            raise NotFoundError("客户不存在")
        if client.confidentiality_level == ConfidentialityLevel.RESTRICTED.value:
            raise BadRequestError("涉密客户项目禁止案例入库")

        kb_repo = KnowledgeBaseRepository(self.db)
        kb = await kb_repo.get_by_id(body.kb_id)
        if not kb or is_marked_deleted(kb):
            raise NotFoundError("知识库不存在")
        assert_tenant_access(self.ctx, kb.tenant_id)

        deliverables = await self.deliverable_repo.list_by_project(self.ctx.tenant_id, project_id)
        candidates = [
            d for d in deliverables
            if d.status == "accepted" and d.attachment_id and not d.kb_document_id
        ]
        if deliverable_ids is not None:
            allowed = set(deliverable_ids)
            candidates = [d for d in candidates if d.id in allowed]
        if not candidates:
            raise BadRequestError("没有可入库的已验收交付物（需含附件且尚未入库）")

        doc_repo = DocumentRepository(self.db)
        kb_storage = await resolve_object_storage_async(kb.tenant_id, self.db)
        document_ids: list[UUID] = []

        for d in candidates:
            att = await self.att_repo.get_by_id(d.attachment_id)
            if not att or is_marked_deleted(att):
                continue
            if not is_kb_upload_allowed(att.filename, att.mime_type):
                continue

            src_storage = await resolve_object_storage_async(att.tenant_id, self.db)
            content = src_storage.storage.download_bytes(att.object_key, att.object_bucket)
            await assert_can_upload_bytes(self.db, kb.tenant_id, len(content))

            doc = await doc_repo.create(
                tenant_id=kb.tenant_id,
                kb_id=kb.id,
                filename=att.filename,
                mime_type=att.mime_type,
                file_size=len(content),
                object_bucket=kb_storage.default_bucket,
                object_key="pending",
                status=DocumentStatus.PENDING,
            )
            object_key = build_object_key(str(kb.tenant_id), str(kb.id), str(doc.id), att.filename)
            doc.object_key = object_key
            kb_storage.storage.upload_bytes(content, object_key, att.mime_type)
            await self.db.flush()

            if body.run_parse:
                from app.tenant.tasks.services.task import TaskService
                from app.workers.tasks.ingest import ingest_document

                task = ingest_document.delay(str(doc.id))
                doc.celery_task_id = task.id
                await TaskService(self.db, self.ctx).create_record(
                    celery_task_id=task.id,
                    task_name="ingest_document",
                    resource_type="document",
                    resource_id=doc.id,
                )

            await apply_storage_delta(self.db, kb.tenant_id, len(content))
            d.kb_document_id = doc.id
            d.type = "kb_document"
            document_ids.append(doc.id)
            await self.db.flush()

        if not document_ids:
            raise BadRequestError(f"交付物附件类型不支持入库。{kb_upload_allowed_hint()}")

        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.archive_case",
            resource_type="biz_project",
            resource_id=project_id,
            detail={"kb_id": str(body.kb_id), "document_count": len(document_ids)},
        )

        return BizArchiveCaseOut(
            project_id=project_id,
            kb_id=body.kb_id,
            archived_count=len(document_ids),
            document_ids=document_ids,
        )
