"""运营端风控 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import RiskSeverity
from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.risk import AdminRiskService
from app.admin.app_ops.schemas import IpBlacklistCreate, RateLimitRuleCreate
from app.admin.app_sys.deps import AdminContext, get_platform_admin
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.infra.db import get_db
from app.core.deps import get_page_params

router = APIRouter()


@router.get("/risk/events")
async def list_risk(
    severity: RiskSeverity | None = None,
    resolved: bool | None = None,
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminRiskService(db).list_risk_events(params, severity=severity, resolved=resolved)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/risk/events/{event_id}/resolve")
async def resolve_risk(
    event_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminRiskService(db).resolve_risk(event_id))


@router.get("/risk/ip-blacklist")
async def list_ips(ctx: AdminContext = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    return ok(await AdminRiskService(db).list_ip_blacklist())


@router.post("/risk/ip-blacklist")
async def add_ip(
    body: IpBlacklistCreate,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminRiskService(db).add_ip_blacklist(body, ctx.admin_id)
    await write_audit_log(
        db, admin_id=ctx.admin_id, action="ip.blacklist.add", request=request, detail=body.model_dump()
    )
    return ok(row)


@router.patch("/risk/ip-blacklist/{ip_id}")
async def toggle_ip(
    ip_id: UUID,
    is_active: bool,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminRiskService(db).toggle_ip(ip_id, is_active))


@router.get("/risk/rate-limits")
async def list_rate_limits(ctx: AdminContext = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    return ok(await AdminRiskService(db).list_rate_limits())


@router.post("/risk/rate-limits")
async def create_rate_limit(
    body: RateLimitRuleCreate,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminRiskService(db).create_rate_limit(body))


@router.patch("/risk/rate-limits/{rule_id}")
async def patch_rate_limit(
    rule_id: UUID,
    is_active: bool | None = None,
    limit_per_minute: int | None = None,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(
        await AdminRiskService(db).update_rate_limit(
            rule_id, is_active=is_active, limit_per_minute=limit_per_minute
        )
    )
