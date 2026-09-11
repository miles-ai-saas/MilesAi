"""应用市场审核核心：通过 / 驳回（Admin 与 Tenant 共用）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.models.marketplace import MarketplaceApp, MarketplaceAppStatus


async def approve_marketplace_app(
    db: AsyncSession,
    app: MarketplaceApp,
    *,
    reviewer_type: Literal["tenant", "admin"],
    reviewer_user_id: UUID | None = None,
    reviewer_admin_id: UUID | None = None,
) -> MarketplaceApp:
    """将待审核应用置为已发布并记录审核人；非 PENDING_REVIEW 时抛 ``BadRequestError``。"""
    if app.status != MarketplaceAppStatus.PENDING_REVIEW:
        raise BadRequestError("仅待审核应用可通过")
    app.status = MarketplaceAppStatus.PUBLISHED
    app.reviewed_at = datetime.now(timezone.utc)
    app.review_note = None
    app.reviewer_type = reviewer_type
    if reviewer_type == "tenant":
        app.reviewed_by = reviewer_user_id
        app.reviewed_by_admin_id = None
    else:
        app.reviewed_by = None
        app.reviewed_by_admin_id = reviewer_admin_id
    await db.flush()
    return app


async def reject_marketplace_app(
    db: AsyncSession,
    app: MarketplaceApp,
    *,
    note: str | None,
    reviewer_type: Literal["tenant", "admin"],
    reviewer_user_id: UUID | None = None,
    reviewer_admin_id: UUID | None = None,
) -> MarketplaceApp:
    """将待审核应用置为已驳回并记录原因/审核人；仅 PENDING_REVIEW 可驳回。"""
    if app.status != MarketplaceAppStatus.PENDING_REVIEW:
        raise BadRequestError("仅待审核应用可驳回")
    app.status = MarketplaceAppStatus.REJECTED
    app.reviewed_at = datetime.now(timezone.utc)
    app.review_note = (note or "").strip() or "未填写驳回原因"
    app.reviewer_type = reviewer_type
    if reviewer_type == "tenant":
        app.reviewed_by = reviewer_user_id
        app.reviewed_by_admin_id = None
    else:
        app.reviewed_by = None
        app.reviewed_by_admin_id = reviewer_admin_id
    await db.flush()
    return app
