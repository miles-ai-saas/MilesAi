"""通用附件：不占知识库文档表，仍计入租户存储配额；key 与 KB 文档路径分离。"""

from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import ColumnElement

from miles_ai.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_allowed_hint
from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.config import get_settings
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from miles_core.tenant import TenantContext, assert_tenant_access
from miles_core.infra.storage import build_attachment_object_key
from miles_core.infra.storage.resolve import resolve_object_storage_async
from miles_ai.rag.parse.media import is_image_file
from miles_core.models.media.attachment import Attachment
from miles_core.logging import get_logger
from miles_portal.tenant.attachments.repositories.attachment import AttachmentRepository
from miles_portal.tenant.attachments.meta import attachments_meta_dict
from miles_portal.tenant.attachments.schemas.meta import AttachmentMetaOut
from miles_portal.tenant.attachments.schemas.attachment import AttachmentOut, AttachmentUploadMeta
from miles_portal.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes
from miles_common.schema import PageParams, PageResult

logger = get_logger(__name__)
settings = get_settings()

# 1x1 透明 PNG（脏数据兜底，避免前端 broken image）
_EMPTY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6260000000000500013fd608ec0000000049454e44ae426082"
)


class AttachmentService(BaseService):
    """通用附件上传/列表/删除；object_key 与 KB 文档路径分离，仍扣 storage 配额。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AttachmentRepository(db)

    async def get_meta(self) -> AttachmentMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return AttachmentMetaOut.model_validate(attachments_meta_dict())

    async def list_attachments(
        self,
        params: PageParams,
        *,
        purpose: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> PageResult[AttachmentOut]:
        """按用途/关联资源过滤，分页列出当前租户未删附件（时间倒序）。"""
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
        """校验类型与配额 → OSS → apply_storage_delta。"""
        if not file.filename:
            raise BadRequestError("文件名不能为空")
        content = await file.read()
        await assert_can_upload_bytes(self.db, self.ctx.tenant_id, len(content))
        mime = file.content_type or "application/octet-stream"
        if not is_kb_upload_allowed(file.filename, mime):
            raise BadRequestError(f"不支持的文件类型: {mime}。{kb_upload_allowed_hint()}")

        storage = await resolve_object_storage_async(self.ctx.tenant_id, self.db)
        att = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            uploaded_by=self.ctx.user_id,
            filename=file.filename,
            mime_type=mime,
            file_size=len(content),
            object_bucket=storage.default_bucket,
            object_key="pending",
            purpose=meta.purpose or "general",
            resource_type=meta.resource_type,
            resource_id=meta.resource_id,
        )
        object_key = build_attachment_object_key(str(self.ctx.tenant_id), str(att.id), file.filename)
        att.object_key = object_key
        storage.storage.upload_bytes(content, object_key, mime)
        await apply_storage_delta(self.db, self.ctx.tenant_id, len(content))
        await self.db.flush()
        await self.db.refresh(att)
        return AttachmentOut.model_validate(att)

    async def get(self, attachment_id: UUID) -> AttachmentOut:
        """读取附件详情（租户鉴权；不存在/已删抛 ``NotFoundError``）。"""
        att = await self._get_or_raise(attachment_id)
        return AttachmentOut.model_validate(att)

    async def read_image_bytes(self, attachment_id: UUID) -> tuple[bytes, str]:
        """校验租户与图片类型后，从对象存储读取字节（供 vision / 内容 API）。
        若文件已不存在（脏数据），返回透明占位图而非 500。"""
        att = await self._get_or_raise(attachment_id)
        if not is_image_file(att.filename, att.mime_type):
            raise BadRequestError("附件不是支持的图片格式（jpeg/png/webp）")
        if not att.object_key or att.object_key == "pending":
            raise BadRequestError("附件文件未就绪")
        try:
            storage = await resolve_object_storage_async(att.tenant_id, self.db)
            data = storage.storage.download_bytes(att.object_key, att.object_bucket)
        except Exception:
            logger.warning(
                "读取附件对象存储失败 attachment_id=%s object_key=%s",
                attachment_id,
                att.object_key,
                exc_info=True,
            )
            data = b""
        if not data:
            data = _EMPTY_PNG
        return data, "image/png"

    async def read_attachment_bytes(self, attachment_id: UUID) -> tuple[bytes, str, str | None]:
        """按租户鉴权读取任意附件字节（不做图片类型校验）。

        返回 ``(data, mime_type, filename)``；不存在/已删抛 ``NotFoundError``，
        文件未就绪抛 ``BadRequestError``。读取失败不吞异常（与 ``read_image_bytes``
        的图片占位兜底不同，音频等需真实字节）。
        """
        att = await self._get_or_raise(attachment_id)
        if not att.object_key or att.object_key == "pending":
            raise BadRequestError("附件文件未就绪")
        storage = await resolve_object_storage_async(att.tenant_id, self.db)
        data = storage.storage.download_bytes(att.object_key, att.object_bucket)
        return data, att.mime_type or "application/octet-stream", att.filename

    async def delete(self, attachment_id: UUID) -> None:
        """软删并尝试删除 OSS 对象（存储回退由 quota 层处理）。"""
        att = await self._get_or_raise(attachment_id)
        if att.object_key and att.object_key != "pending":
            try:
                storage = await resolve_object_storage_async(att.tenant_id, self.db)
                storage.storage.delete_object(att.object_key, att.object_bucket)
            except Exception:
                logger.warning(
                    "删除附件 OSS 对象失败 attachment_id=%s object_key=%s",
                    attachment_id,
                    att.object_key,
                    exc_info=True,
                )
        await mark_deleted(self.db, att)
        await apply_storage_delta(self.db, att.tenant_id, 0)

    async def _get_or_raise(self, attachment_id: UUID) -> Attachment:
        """按 ID 取未删附件并校验租户归属；缺失或跨租户均抛 ``NotFoundError``。"""
        att = await self.repo.get_by_id(attachment_id)
        if not att or is_marked_deleted(att):
            raise NotFoundError("附件不存在")
        assert_tenant_access(self.ctx, att.tenant_id)
        return att
