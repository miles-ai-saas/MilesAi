"""知识库与附件的租户配额校验与存储用量回写。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, ForbiddenError
from app.core.soft_delete import not_deleted
from app.models.attachment import Attachment
from app.models.kb import Document, KnowledgeBase
from app.models.system import SystemConfig
from app.models.tenant import Tenant

DEFAULT_MAX_FILE_MB = 50


def _config_int(raw: object, default: int) -> int:
    if raw is None:
        return default
    if isinstance(raw, dict) and "value" in raw:
        raw = raw["value"]
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return default


async def get_max_file_mb(db: AsyncSession) -> int:
    row = await db.scalar(
        select(SystemConfig.value).where(SystemConfig.key == "ingest.max_file_mb")
    )
    return _config_int(row, DEFAULT_MAX_FILE_MB)


async def _load_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise ForbiddenError("租户不存在")
    return tenant


async def count_knowledge_bases(db: AsyncSession, tenant_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == tenant_id, not_deleted(KnowledgeBase))
        )
        or 0
    )


async def sum_storage_bytes(db: AsyncSession, tenant_id: UUID) -> int:
    doc_bytes = await db.scalar(
        select(func.coalesce(func.sum(Document.file_size), 0)).where(
            Document.tenant_id == tenant_id,
            not_deleted(Document),
        )
    )
    att_bytes = await db.scalar(
        select(func.coalesce(func.sum(Attachment.file_size), 0)).where(
            Attachment.tenant_id == tenant_id,
            not_deleted(Attachment),
        )
    )
    return int(doc_bytes or 0) + int(att_bytes or 0)


async def assert_can_create_kb(db: AsyncSession, tenant_id: UUID) -> None:
    tenant = await _load_tenant(db, tenant_id)
    count = await count_knowledge_bases(db, tenant_id)
    if count >= tenant.max_knowledge_bases:
        raise ForbiddenError(
            f"知识库数量已达上限（{tenant.max_knowledge_bases}），请联系管理员提升配额"
        )


async def assert_can_upload_bytes(
    db: AsyncSession,
    tenant_id: UUID,
    file_size: int,
) -> None:
    if file_size <= 0:
        raise BadRequestError("文件内容为空")
    max_mb = await get_max_file_mb(db)
    max_bytes = max_mb * 1024 * 1024
    if file_size > max_bytes:
        raise BadRequestError(f"单文件不能超过 {max_mb} MB")

    tenant = await _load_tenant(db, tenant_id)
    used_bytes = await sum_storage_bytes(db, tenant_id)
    projected_mb = (used_bytes + file_size + 1024 * 1024 - 1) // (1024 * 1024)
    if projected_mb > tenant.max_storage_mb:
        raise ForbiddenError(
            f"存储空间不足（已用约 {used_bytes // (1024 * 1024)} MB / 上限 {tenant.max_storage_mb} MB）"
        )


async def apply_storage_delta(db: AsyncSession, tenant_id: UUID, delta_bytes: int) -> None:
    """按字节增量更新租户 storage_used_mb（与运营侧统计口径一致）。"""
    if delta_bytes == 0:
        return
    tenant = await _load_tenant(db, tenant_id)
    used_bytes = await sum_storage_bytes(db, tenant_id)
    tenant.storage_used_mb = max(0, used_bytes // (1024 * 1024))
    await db.flush()


async def get_kb_quota_out(db: AsyncSession, tenant_id: UUID) -> dict:
    tenant = await _load_tenant(db, tenant_id)
    used_bases = await count_knowledge_bases(db, tenant_id)
    used_bytes = await sum_storage_bytes(db, tenant_id)
    return {
        "used_knowledge_bases": used_bases,
        "max_knowledge_bases": tenant.max_knowledge_bases,
        "used_storage_mb": used_bytes // (1024 * 1024),
        "max_storage_mb": tenant.max_storage_mb,
        "max_file_mb": await get_max_file_mb(db),
    }
