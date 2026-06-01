"""将历史 chat_generated / flow_generated 附件登记为 media_assets。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.tenant import TenantContext
from app.integrations.generative.persist import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from app.models.media.attachment import Attachment
from app.models.media.media_asset import MediaAsset
from app.tenant.media_assets.repositories.media_asset import MediaAssetRepository
from app.tenant.media_assets.services.media_asset import register_media_asset

_GENERATED_PURPOSES = (PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED)


async def backfill_media_assets(
    db: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """
    为尚无 media_assets 行的生成附件补登记。

    返回 ``scanned`` / ``created`` / ``skipped`` / ``errors`` 计数。
    """
    filters = [
        Attachment.purpose.in_(_GENERATED_PURPOSES),
        not_deleted(Attachment),
        Attachment.object_key != "pending",
        Attachment.object_key != "",
    ]
    if tenant_id is not None:
        filters.append(Attachment.tenant_id == tenant_id)

    stmt = select(Attachment).where(*filters).order_by(Attachment.created_at.asc())
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)

    attachments = list((await db.execute(stmt)).scalars().all())
    repo = MediaAssetRepository(db)
    stats = {"scanned": 0, "created": 0, "skipped": 0, "errors": 0}

    for att in attachments:
        stats["scanned"] += 1
        existing = await repo.get_one(MediaAsset.attachment_id == att.id)
        if existing and not is_marked_deleted(existing):
            stats["skipped"] += 1
            continue
        if existing:
            stats["skipped"] += 1
            continue

        if dry_run:
            stats["created"] += 1
            continue

        ctx = TenantContext(
            user_id=att.uploaded_by,
            tenant_id=att.tenant_id,
            username="backfill",
            is_superuser=True,
            permissions=frozenset(),
        )
        try:
            await register_media_asset(
                db,
                ctx,
                attachment_id=att.id,
                purpose=att.purpose,
                source_ref_type=att.resource_type,
                source_ref_id=att.resource_id,
            )
            stats["created"] += 1
        except Exception:
            stats["errors"] += 1

    if not dry_run:
        await db.commit()
    return stats


async def run_backfill_media_assets(
    *,
    tenant_id: UUID | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    from app.infra.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await backfill_media_assets(
            db,
            tenant_id=tenant_id,
            dry_run=dry_run,
            limit=limit,
        )
