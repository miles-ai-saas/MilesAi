"""生成物写入对象存储与 sys_attachments。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.infra.storage import build_attachment_object_key, upload_bytes
from app.tenant.attachments.repositories.attachment import AttachmentRepository
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes

settings = get_settings()

# sys_attachments.purpose：区分对话工具产出与画布节点产出
PURPOSE_CHAT_GENERATED = "chat_generated"
PURPOSE_FLOW_GENERATED = "flow_generated"


async def persist_generated_bytes(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    data: bytes,
    filename: str,
    mime_type: str,
    purpose: str = PURPOSE_CHAT_GENERATED,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
) -> UUID:
    """上传字节并创建附件记录，返回 attachment_id。"""
    await assert_can_upload_bytes(db, ctx.tenant_id, len(data))
    repo = AttachmentRepository(db)
    att = await repo.create(
        tenant_id=ctx.tenant_id,
        uploaded_by=ctx.user_id,
        filename=filename,
        mime_type=mime_type,
        file_size=len(data),
        object_bucket=settings.object_storage_bucket,
        object_key="pending",
        purpose=purpose,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    object_key = build_attachment_object_key(
        str(ctx.tenant_id), str(att.id), filename
    )
    att.object_key = object_key
    upload_bytes(data, object_key, mime_type)
    await apply_storage_delta(db, ctx.tenant_id, len(data))
    await db.flush()
    await db.refresh(att)
    return att.id
