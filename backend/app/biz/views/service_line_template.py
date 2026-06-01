"""服务线阶段模板 HTTP API。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.service_line_template import BizServiceLineTemplateOut, BizServiceLineTemplateUpsert
from app.biz.services.service_line_template_admin import ServiceLineTemplateAdminService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


class ServiceLineTemplateUpsertBody(BaseModel):
    stages: list[str] = Field(min_length=1)
    is_active: bool = True
    ai_config: dict | None = None


def _svc(db: AsyncSession, ctx: TenantContext) -> ServiceLineTemplateAdminService:
    return ServiceLineTemplateAdminService(db, ctx)


@router.get("", response_model=ApiResponse[list[BizServiceLineTemplateOut]])
async def list_service_line_templates(
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_templates())


@router.put("/{service_line}", response_model=ApiResponse[BizServiceLineTemplateOut])
async def upsert_service_line_template(
    service_line: str,
    body: ServiceLineTemplateUpsertBody,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    payload = BizServiceLineTemplateUpsert(stages=body.stages, is_active=body.is_active, ai_config=body.ai_config)
    return ok(await _svc(db, ctx).upsert(service_line, payload))


@router.delete("/{service_line}", response_model=ApiResponse[BizServiceLineTemplateOut])
async def reset_service_line_template(
    service_line: str,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).reset(service_line))
