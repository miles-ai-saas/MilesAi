"""生成物写入对象存储与 sys_attachments。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.infra.storage import build_attachment_object_key
from app.infra.storage.resolve import resolve_object_storage_async
from app.integrations.generative.constants import (  # noqa: F401  # re-export 保路径
    PURPOSE_CHAT_GENERATED,
    PURPOSE_FLOW_GENERATED,
)
from app.tenant.attachments.repositories.attachment import AttachmentRepository
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes

settings = get_settings()


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
    storage = await resolve_object_storage_async(ctx.tenant_id, db)
    att = await repo.create(
        tenant_id=ctx.tenant_id,
        uploaded_by=ctx.user_id,
        filename=filename,
        mime_type=mime_type,
        file_size=len(data),
        object_bucket=storage.default_bucket,
        object_key="pending",
        purpose=purpose,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    object_key = build_attachment_object_key(str(ctx.tenant_id), str(att.id), filename)
    att.object_key = object_key
    storage.storage.upload_bytes(data, object_key, mime_type)
    await apply_storage_delta(db, ctx.tenant_id, len(data))
    await db.flush()
    await db.refresh(att)
    return att.id
