"""业务仪表盘 HTTP API，路由前缀 `/biz/dashboard`。

提供业务总览统计数据，包含 GET /summary 总览端点，返回客户数、商机数、项目数、合同额等概览指标。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.dashboard import DashboardSummaryOut
from app.biz.services.dashboard import DashboardService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


@router.get("/summary", response_model=ApiResponse[DashboardSummaryOut])
async def get_dashboard_summary(
    ctx: TenantContext = Depends(require_permissions("biz:dashboard:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取业务仪表盘总览统计，包括客户数、商机数、项目数、合同额等关键指标。"""
    return ok(await DashboardService(db, ctx).get_summary())
