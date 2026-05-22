"""工作台概览 HTTP API（租户资源用量与快捷入口统计）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.workbench.schemas.overview import WorkbenchOverviewOut
from app.tenant.workbench.services.overview import WorkbenchOverviewService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.infra.db import get_db
from app.core.deps import get_tenant_context
from app.core.tenant import TenantContext

router = APIRouter()


@router.get("/overview", response_model=ApiResponse[WorkbenchOverviewOut])
async def workbench_overview(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """工作台概览统计（聚合 COUNT，替代多路列表分页请求）。"""
    return ok(await WorkbenchOverviewService(db, ctx).overview())
