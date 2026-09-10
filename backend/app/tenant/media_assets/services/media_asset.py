"""媒体资产：登记、列表、升格入库。

登记链路：``persist_generated_bytes`` → ``register_media_asset``（生图/生视频/TTS 附件）。
升格入库：图片/视频附件 → KB Document → 可选 ``ingest_document`` 解析入库。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.config import get_settings
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.infra.storage import build_object_key
from app.infra.storage.resolve import resolve_object_storage_async
from app.integrations.generative.constants import PURPOSE_FLOW_GENERATED
from app.models.media.attachment import Attachment
from app.models.kb import DocumentStatus
from app.models.media.media_asset import MediaAsset
from app.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_allowed_hint
from app.tenant.attachments.repositories.attachment import AttachmentRepository
from app.tenant.attachments.schemas.attachment import AttachmentOut
from app.tenant.kb.repositories.kb import DocumentRepository, KnowledgeBaseRepository
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes
from app.tenant.media_assets.repositories.media_asset import MediaAssetRepository
from app.tenant.media_assets.schemas.media_asset import (
    MediaAssetOut,
    MediaAssetUpdate,
    PromoteToKbRequest,
)

settings = get_settings()

SOURCE_AGENT_TOOL = "agent_tool"
SOURCE_FLOW_NODE = "flow_node"


def _source_from_purpose(purpose: str) -> str:
    """根据附件 purpose 推断资产来源（agent_tool / flow_node）。"""
    if purpose == PURPOSE_FLOW_GENERATED:
        return SOURCE_FLOW_NODE
    return SOURCE_AGENT_TOOL


def _kind_from_mime(mime_type: str) -> str:
    """MIME → 资产 kind（video / image）。"""
    if mime_type.startswith("video/"):
        return "video"
    return "image"


async def register_media_asset(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    attachment_id: UUID,
    purpose: str,
    prompt: str | None = None,
    model_config_id: UUID | None = None,
    kind: str | None = None,
    source: str | None = None,
    source_ref_type: str | None = None,
    source_ref_id: UUID | None = None,
    cover_attachment_id: UUID | None = None,
) -> MediaAsset:
    """生成物落库后登记资产（同一 attachment 仅一条，已存在则跳过）。"""
    att_repo = AttachmentRepository(db)
    att = await att_repo.get_by_id(attachment_id)
    if not att or is_marked_deleted(att):
        raise NotFoundError("附件不存在")
    assert_tenant_access(ctx, att.tenant_id)

    repo = MediaAssetRepository(db)
    existing = await repo.get_one(MediaAsset.attachment_id == attachment_id)
    if existing and not is_marked_deleted(existing):
        if cover_attachment_id and not existing.cover_attachment_id:
            existing.cover_attachment_id = cover_attachment_id
            await db.flush()
            await db.refresh(existing)
        return existing

    resolved_kind = kind or _kind_from_mime(att.mime_type)
    resolved_source = source or _source_from_purpose(purpose)
    title = att.filename

    row = await repo.create(
        tenant_id=ctx.tenant_id,
        attachment_id=attachment_id,
        cover_attachment_id=cover_attachment_id,
        kind=resolved_kind,
        source=resolved_source,
        source_ref_type=source_ref_type or att.resource_type,
        source_ref_id=source_ref_id or att.resource_id,
        prompt=(prompt or "").strip() or None,
        model_config_id=model_config_id,
        title=title,
        tags=None,
        kb_id=None,
        kb_document_id=None,
        promoted_at=None,
        created_by=ctx.user_id,
    )
    await db.flush()
    await db.refresh(row)
    return row


class MediaAssetService(BaseService):
    """租户生成素材库：分页列表、元数据编辑、删除与升格 KB。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = MediaAssetRepository(db)
        self.att_repo = AttachmentRepository(db)

    async def list_assets(
        self,
        params: PageParams,
        *,
        kind: str | None = None,
        source: str | None = None,
        has_kb_document: bool | None = None,
    ) -> PageResult[MediaAssetOut]:
        """分页列出媒体资产，可按 kind/source/是否已入库筛选。"""
        filters: list[ColumnElement[bool]] = [
            MediaAsset.tenant_id == self.ctx.tenant_id,
            not_deleted(MediaAsset),
        ]
        if kind:
            filters.append(MediaAsset.kind == kind)
        if source:
            filters.append(MediaAsset.source == source)
        if has_kb_document is True:
            filters.append(MediaAsset.kb_document_id.isnot(None))
        elif has_kb_document is False:
            filters.append(MediaAsset.kb_document_id.is_(None))

        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=MediaAsset.created_at.desc(),
        )
        items = [await self._to_out(row) for row in page.items]
        return PageResult(items=items, total=page.total, page=page.page, size=page.size)

    async def get(self, asset_id: UUID) -> MediaAssetOut:
        """单条详情（含 attachment / cover 预览元数据）。"""
        row = await self._get_or_raise(asset_id)
        return await self._to_out(row)

    async def update(self, asset_id: UUID, body: MediaAssetUpdate) -> MediaAssetOut:
        """更新标题与标签。"""
        row = await self._get_or_raise(asset_id)
        if body.title is not None:
            row.title = body.title.strip() or None
        if body.tags is not None:
            row.tags = body.tags
        await self.db.flush()
        await self.db.refresh(row)
        return await self._to_out(row)

    async def delete(self, asset_id: UUID) -> None:
        """软删媒体资产记录（不删底层 attachment）。"""
        row = await self._get_or_raise(asset_id)
        await mark_deleted(self.db, row)

    async def promote_to_kb(self, asset_id: UUID, body: PromoteToKbRequest) -> MediaAssetOut:
        """将生成物升格为 KB 文档；视频默认以 Markdown 描述入库供检索。"""
        row = await self._get_or_raise(asset_id)
        if row.kb_document_id:
            raise BadRequestError("该资产已升格入库，请勿重复操作")

        att = await self._get_attachment_or_raise(row.attachment_id)
        is_video = row.kind == "video" or att.mime_type.startswith("video/")

        if is_video:
            content, filename, mime = self._build_video_promote_document(row, att, body)
        else:
            storage = await resolve_object_storage_async(att.tenant_id, self.db)
            content = storage.storage.download_bytes(att.object_key, att.object_bucket)
            filename = (body.filename or row.title or att.filename).strip()
            if not filename:
                raise BadRequestError("文件名不能为空")
            mime = att.mime_type
            if not is_kb_upload_allowed(filename, mime):
                raise BadRequestError(f"文件类型不支持入库。{kb_upload_allowed_hint()}")

        kb_repo = KnowledgeBaseRepository(self.db)
        kb = await kb_repo.get_by_id(body.kb_id)
        if not kb or is_marked_deleted(kb):
            raise NotFoundError("知识库不存在")
        assert_tenant_access(self.ctx, kb.tenant_id)

        await assert_can_upload_bytes(self.db, kb.tenant_id, len(content))

        doc_repo = DocumentRepository(self.db)
        kb_storage = await resolve_object_storage_async(kb.tenant_id, self.db)
        doc = await doc_repo.create(
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            filename=filename,
            mime_type=mime,
            file_size=len(content),
            object_bucket=kb_storage.default_bucket,
            object_key="pending",
            status=DocumentStatus.PENDING,
        )
        object_key = build_object_key(str(kb.tenant_id), str(kb.id), str(doc.id), filename)
        doc.object_key = object_key
        kb_storage.storage.upload_bytes(content, object_key, mime)
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
        row.kb_id = kb.id
        row.kb_document_id = doc.id
        row.promoted_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(row)
        return await self._to_out(row)

    async def _to_out(self, row: MediaAsset) -> MediaAssetOut:
        """ORM → API，附带 attachment / cover 嵌套对象。"""
        att = await self.att_repo.get_by_id(row.attachment_id)
        attachment_out = AttachmentOut.model_validate(att) if att and not is_marked_deleted(att) else None
        cover_out = None
        if row.cover_attachment_id:
            cover_att = await self.att_repo.get_by_id(row.cover_attachment_id)
            if cover_att and not is_marked_deleted(cover_att):
                cover_out = AttachmentOut.model_validate(cover_att)
        data = MediaAssetOut.model_validate(row)
        return data.model_copy(update={"attachment": attachment_out, "cover_attachment": cover_out})

    def _build_video_promote_document(
        self,
        row: MediaAsset,
        att: Attachment,
        body: PromoteToKbRequest,
    ) -> tuple[bytes, str, str]:
        """视频升格：以生成描述 Markdown 入库供 RAG 检索，原视频仍在 attachment。"""
        base = (body.filename or row.title or att.filename or "generated-video").strip()
        if not base.lower().endswith(".md"):
            base = f"{base.rsplit('.', 1)[0] if '.' in base else base}.md"
        prompt = (row.prompt or "").strip() or "（无记录提示词）"
        text = (
            f"# 生成视频资产\n\n"
            f"- **媒体资产 ID**：`{row.id}`\n"
            f"- **视频附件 ID**：`{att.id}`\n"
            f"- **原始文件名**：{att.filename}\n"
            f"- **MIME**：{att.mime_type}\n\n"
            f"## 生成描述（检索用）\n\n{prompt}\n\n"
            f"## 说明\n\n"
            f"本条为 AI 生成视频的文字索引；播放请在「生成素材」中打开对应视频附件。\n"
        )
        return text.encode("utf-8"), base, "text/markdown"

    async def _get_or_raise(self, asset_id: UUID) -> MediaAsset:
        """加载资产并校验租户归属。"""
        row = await self.repo.get_by_id(asset_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("媒体资产不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _get_attachment_or_raise(self, attachment_id: UUID) -> Attachment:
        """加载附件并确认 object_key 已就绪（非 pending）。"""
        att = await self.att_repo.get_by_id(attachment_id)
        if not att or is_marked_deleted(att):
            raise NotFoundError("附件不存在")
        assert_tenant_access(self.ctx, att.tenant_id)
        if not att.object_key or att.object_key == "pending":
            raise BadRequestError("附件文件未就绪")
        return att
