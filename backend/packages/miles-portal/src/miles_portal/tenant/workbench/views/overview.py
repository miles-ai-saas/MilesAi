"""工作台概览 HTTP API（租户资源用量与快捷入口统计）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_portal.tenant.workbench.schemas.overview import WorkbenchOverviewOut
from miles_portal.tenant.workbench.services.overview import WorkbenchOverviewService
from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.infra.db import get_db
from miles_core.deps import get_tenant_context
from miles_core.tenant import TenantContext

router = APIRouter()


@router.get("/overview", response_model=ApiResponse[WorkbenchOverviewOut])
async def workbench_overview(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """工作台概览统计（聚合 COUNT，替代多路列表分页请求）。"""
    return ok(await WorkbenchOverviewService(db, ctx).overview())
