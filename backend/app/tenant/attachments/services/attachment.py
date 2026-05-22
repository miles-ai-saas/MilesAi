from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import ColumnElement

from app.rag.parse import file_extension, is_audio_file, is_image_file
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.config import get_settings
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.infra.storage import build_attachment_object_key, delete_object, upload_bytes
from app.models.attachment import Attachment
from app.tenant.attachments.repositories.attachment import AttachmentRepository
from app.tenant.attachments.schemas.attachment import AttachmentOut, AttachmentUploadMeta
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes
from app.common.schema import PageParams, PageResult

settings = get_settings()

ALLOWED_MIMES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/octet-stream",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
}

_ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".webm",
}


def _is_allowed_upload(filename: str, mime: str) -> bool:
    ext = file_extension(filename)
    if mime in ALLOWED_MIMES or ext in _ALLOWED_EXTENSIONS:
        return True
    return is_image_file(filename, mime) or is_audio_file(filename, mime)


class AttachmentService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AttachmentRepository(db)

    async def list_attachments(
        self,
        params: PageParams,
        *,
        purpose: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> PageResult[AttachmentOut]:
        filters: list[ColumnElement[bool]] = [
            Attachment.tenant_id == self.ctx.tenant_id,
            not_deleted(Attachment),
        ]
        if purpose:
            filters.append(Attachment.purpose == purpose)
        if resource_type:
            filters.append(Attachment.resource_type == resource_type)
        if resource_id:
            filters.append(Attachment.resource_id == resource_id)
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=Attachment.created_at.desc(),
        )
        return PageResult(
            items=[AttachmentOut.model_validate(a) for a in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def upload(
        self,
        file: UploadFile,
        meta: AttachmentUploadMeta,
    ) -> AttachmentOut:
        if not file.filename:
            raise BadRequestError("文件名不能为空")
        content = await file.read()
        await assert_can_upload_bytes(self.db, self.ctx.tenant_id, len(content))
        mime = file.content_type or "application/octet-stream"
        if not _is_allowed_upload(file.filename, mime):
            raise BadRequestError(
                f"不支持的文件类型: {mime}。"
                "支持 TXT/MD/PDF、图片（JPG/PNG/WebP）、音频（MP3/WAV）"
            )

        att = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            uploaded_by=self.ctx.user_id,
            filename=file.filename,
            mime_type=mime,
            file_size=len(content),
            object_bucket=settings.object_storage_bucket,
            object_key="pending",
            purpose=meta.purpose or "general",
            resource_type=meta.resource_type,
            resource_id=meta.resource_id,
        )
        object_key = build_attachment_object_key(
            str(self.ctx.tenant_id), str(att.id), file.filename
        )
        att.object_key = object_key
        upload_bytes(content, object_key, mime)
        await apply_storage_delta(self.db, self.ctx.tenant_id, len(content))
        await self.db.flush()
        await self.db.refresh(att)
        return AttachmentOut.model_validate(att)

    async def get(self, attachment_id: UUID) -> AttachmentOut:
        att = await self._get_or_raise(attachment_id)
        return AttachmentOut.model_validate(att)

    async def delete(self, attachment_id: UUID) -> None:
        att = await self._get_or_raise(attachment_id)
        if att.object_key and att.object_key != "pending":
            try:
                delete_object(att.object_key, att.object_bucket)
            except Exception:
                pass
        await mark_deleted(self.db, att)
        await apply_storage_delta(self.db, att.tenant_id, 0)

    async def _get_or_raise(self, attachment_id: UUID) -> Attachment:
        att = await self.repo.get_by_id(attachment_id)
        if not att or is_marked_deleted(att):
            raise NotFoundError("附件不存在")
        assert_tenant_access(self.ctx, att.tenant_id)
        return att
