"""运营控制台 HTTP API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_ops.schemas.dashboard import AdminDashboardSummaryOut
from miles_admin.app_ops.services.dashboard import AdminDashboardService
from miles_admin.app_sys.deps import AdminContext, get_platform_admin
from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.infra.db import get_db

router = APIRouter()


@router.get("/dashboard/summary", response_model=ApiResponse[AdminDashboardSummaryOut])
async def dashboard_summary(
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    _ = ctx
    return ok(await AdminDashboardService(db).get_summary())
