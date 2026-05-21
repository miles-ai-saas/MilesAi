from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permissions
from app.common.response import ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse
from app.app_tenant.monitor.schemas.monitor import AlertConfig, MonitorReport, MonitorStats
from app.app_tenant.monitor.services.monitor import MonitorService

router = APIRouter()


@router.get("/stats", response_model=ApiResponse[MonitorStats])
async def monitor_stats(
    ctx: TenantContext = Depends(require_permissions("monitor:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await MonitorService(db, ctx).stats())


@router.get("/report", response_model=ApiResponse[MonitorReport])
async def monitor_report(
    ctx: TenantContext = Depends(require_permissions("monitor:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await MonitorService(db, ctx).report())


@router.get("/report/export")
async def export_report(
    ctx: TenantContext = Depends(require_permissions("monitor:read")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await MonitorService(db, ctx).export_report_csv()
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=aiengine-report.csv"},
    )


@router.get("/health", response_model=ApiResponse[dict])
async def monitor_health(
    ctx: TenantContext = Depends(require_permissions("monitor:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await MonitorService(db, ctx).health())


@router.get("/alerts", response_model=ApiResponse[AlertConfig])
async def get_alerts(
    ctx: TenantContext = Depends(require_permissions("monitor:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await MonitorService(db, ctx).get_alert_config())


@router.put("/alerts", response_model=ApiResponse[AlertConfig])
async def save_alerts(
    body: AlertConfig,
    ctx: TenantContext = Depends(require_permissions("monitor:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await MonitorService(db, ctx).save_alert_config(body))


@router.post("/alerts/test", response_model=ApiResponse[dict])
async def test_alerts(
    body: AlertConfig,
    ctx: TenantContext = Depends(require_permissions("monitor:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await MonitorService(db, ctx).test_alert(body))
