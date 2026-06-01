"""业务中心 CSV 导出 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.services.export import BizExportService
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> BizExportService:
    return BizExportService(db, ctx)


@router.get("/projects.csv")
async def export_projects(
    client_id: UUID | None = Query(None),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await _svc(db, ctx).export_projects_csv(client_id=client_id, status=status)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=biz-projects.csv"},
    )


@router.get("/opportunities.csv")
async def export_opportunities(
    client_id: UUID | None = Query(None),
    stage: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:read")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await _svc(db, ctx).export_opportunities_csv(client_id=client_id, stage=stage)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=biz-opportunities.csv"},
    )


@router.get("/clients.csv")
async def export_clients(
    search: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:client:read")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await _svc(db, ctx).export_clients_csv(search=search)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=biz-clients.csv"},
    )


@router.get("/contracts.csv")
async def export_contracts(
    client_id: UUID | None = Query(None),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:contract:read")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await _svc(db, ctx).export_contracts_csv(client_id=client_id, status=status)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=biz-contracts.csv"},
    )


@router.get("/payments.csv")
async def export_payments(
    ctx: TenantContext = Depends(require_permissions("biz:finance:read")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await _svc(db, ctx).export_payments_csv()
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=biz-payments.csv"},
    )
