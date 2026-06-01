"""工作包独立 API（阶段推进等）。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.project import BizWorkPackageOut
from app.biz.services.project import ProjectService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ProjectService:
    return ProjectService(db, ctx)


@router.post("/{wp_id}/advance-stage", response_model=ApiResponse[BizWorkPackageOut])
async def advance_work_package_stage(
    wp_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """推进工作包到服务线模板的下一阶段。"""
    return ok(await _svc(db, ctx).advance_work_package_stage(wp_id))
