"""生成物写入对象存储与 sys_attachments（L1）。

对象存储客户端为同步实现，故写入经 ``asyncio.to_thread`` 离线，避免阻塞事件循环
（见 ``tests/test_no_blocking_calls_in_async.py``）。

上传前 ``await db.commit()``：附件行以 ``object_key=pending`` 落库后释放连接，
避免 OSS 上传期间 idle-in-transaction；上传成功后再写最终 key 与配额增量。
"""

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.config import get_settings
from miles_core.infra.storage import build_attachment_object_key
from miles_core.infra.storage.resolve import resolve_object_storage_async
from miles_core.tenant import TenantContext
from miles_integrations.generative.constants import PURPOSE_CHAT_GENERATED
from miles_portal.tenant.attachments.repositories.attachment import AttachmentRepository
from miles_portal.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes

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
    await db.flush()
    object_key = build_attachment_object_key(str(ctx.tenant_id), str(att.id), filename)
    # 释放事务：随后 OSS 上传可能数秒；失败时附件仍为 pending，可后续清理。
    await db.commit()
    await asyncio.to_thread(storage.storage.upload_bytes, data, object_key, mime_type)
    att.object_key = object_key
    await apply_storage_delta(db, ctx.tenant_id, len(data))
    await db.flush()
    await db.refresh(att)
    return att.id
