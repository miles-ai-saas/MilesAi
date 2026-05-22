from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import require_permissions
from app.common.response import ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse
from app.tenant.system.schemas.config import (
    ConfigDefinitionOut,
    RuntimeInfoOut,
    SystemConfigOut,
    SystemConfigUpsert,
)
from app.tenant.system.services.config import SystemConfigService

router = APIRouter()


@router.get("/definitions", response_model=ApiResponse[list[ConfigDefinitionOut]])
async def list_config_definitions(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SystemConfigService(db, ctx).list_definitions())


@router.get("/runtime", response_model=ApiResponse[RuntimeInfoOut])
async def get_runtime_info(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SystemConfigService(db, ctx).runtime_info())


@router.get("", response_model=ApiResponse[list[SystemConfigOut]])
async def list_configs(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SystemConfigService(db, ctx).list_configs())


@router.put("/{key}", response_model=ApiResponse[SystemConfigOut])
async def upsert_config(
    key: str,
    body: SystemConfigUpsert,
    ctx: TenantContext = Depends(require_permissions("system:config:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SystemConfigService(db, ctx).upsert_config(key, body))
