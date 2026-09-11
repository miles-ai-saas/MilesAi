"""运营端风控 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.models import RiskSeverity
from miles_admin.app_ops.services.audit import write_audit_log
from miles_admin.app_ops.services.risk import AdminRiskService
from miles_admin.app_ops.schemas import IpBlacklistCreate, RateLimitRuleCreate, RateLimitRuleUpdate
from miles_admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from miles_common.response import ok, page_ok
from miles_common.schema import PageParams
from miles_core.infra.db import get_db
from miles_core.deps import get_page_params

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
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("security")),
    db: AsyncSession = Depends(get_db),
):
    event = await AdminRiskService(db).resolve_risk(event_id)
    await write_audit_log(db, admin_id=ctx.admin_id, action="risk.resolve", request=request, detail={"event_id": str(event_id)})
    return ok(event)


@router.get("/risk/ip-blacklist")
async def list_ips(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminRiskService(db).list_ip_blacklist(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/risk/ip-blacklist")
async def add_ip(
    body: IpBlacklistCreate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("security")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminRiskService(db).add_ip_blacklist(body, ctx.admin_id)
    await write_audit_log(db, admin_id=ctx.admin_id, action="ip.blacklist.add", request=request, detail=body.model_dump())
    return ok(row)


@router.patch("/risk/ip-blacklist/{ip_id}")
async def toggle_ip(
    ip_id: UUID,
    is_active: bool,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("security")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminRiskService(db).toggle_ip(ip_id, is_active)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="risk.ip.toggle",
        request=request,
        detail={"ip_id": str(ip_id), "is_active": is_active},
    )
    return ok(row)


@router.get("/risk/rate-limits")
async def list_rate_limits(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminRiskService(db).list_rate_limits(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/risk/rate-limits")
async def create_rate_limit(
    body: RateLimitRuleCreate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("security")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminRiskService(db).create_rate_limit(body)
    await write_audit_log(db, admin_id=ctx.admin_id, action="risk.rule.create", request=request, detail=body.model_dump())
    return ok(row)


@router.patch("/risk/rate-limits/{rule_id}")
async def patch_rate_limit(
    rule_id: UUID,
    body: RateLimitRuleUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("security")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminRiskService(db).update_rate_limit(rule_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="risk.rule.update",
        request=request,
        detail={"rule_id": str(rule_id), **body.model_dump(exclude_unset=True)},
    )
    return ok(row)
