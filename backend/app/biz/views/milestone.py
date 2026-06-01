"""里程碑到期 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.milestone import BizMilestoneDueOut
from app.biz.services.milestone_due import MilestoneDueService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> MilestoneDueService:
    return MilestoneDueService(db, ctx)


@router.get("/due", response_model=ApiResponse[list[BizMilestoneDueOut]])
async def list_due_milestones(
    days: int = Query(7, ge=0, le=90),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """列出即将到期或已逾期的里程碑。"""
    return ok(await _svc(db, ctx).list_due(days=days))
