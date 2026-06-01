"""业务中心站内通知 HTTP API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.notification import BizNotificationsOut
from app.biz.services.milestone_due import MilestoneDueService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


@router.get("", response_model=ApiResponse[BizNotificationsOut])
async def get_notifications(
    days: int = Query(7, ge=0, le=30),
    limit: int = Query(20, ge=1, le=50),
    ctx: TenantContext = Depends(require_permissions("biz:dashboard:read")),
    db: AsyncSession = Depends(get_db),
):
    """返回即将到期里程碑等站内提醒。"""
    milestones = await MilestoneDueService(db, ctx).list_due(days=days, limit=limit)
    return ok(
        BizNotificationsOut(
            due_milestone_count=len(milestones),
            due_milestones=milestones,
        )
    )
