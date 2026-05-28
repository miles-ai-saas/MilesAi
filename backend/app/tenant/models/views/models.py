"""模型供应商 HTTP API：内置目录、租户自定义模型与 BYOK 凭证。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import require_permissions
from app.common.response import ok
from app.core.tenant import TenantContext
from app.tenant.models.schemas.model import (
    ModelBuiltinCredentialsIn,
    ModelCatalogMetaOut,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
)
from app.tenant.models.services.model import ModelService
from app.common.schema import ApiResponse

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ModelService:
    return ModelService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[ModelCatalogMetaOut])
async def model_catalog_meta(
    ctx: TenantContext = Depends(require_permissions("model:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).catalog_meta())


@router.post("", response_model=ApiResponse[ModelConfigOut])
async def create_model_config(
    body: ModelConfigCreate,
    ctx: TenantContext = Depends(require_permissions("model:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_config(body))


@router.get("", response_model=ApiResponse[list[ModelConfigOut]])
async def list_model_configs(
    vendor: str | None = Query(None),
    model_type: str | None = Query(None),
    source: str | None = Query(None, description="builtin | custom"),
    q: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("model:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_configs(vendor=vendor, model_type=model_type, source=source, q=q))


@router.patch("/{config_id}", response_model=ApiResponse[ModelConfigOut])
async def update_model_config(
    config_id: UUID,
    body: ModelConfigUpdate,
    ctx: TenantContext = Depends(require_permissions("model:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_config(config_id, body))


@router.delete("/{config_id}", response_model=ApiResponse[None])
async def delete_model_config(
    config_id: UUID,
    ctx: TenantContext = Depends(require_permissions("model:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_config(config_id)
    return ok(message="已删除")


@router.put("/builtin/{config_id}/credentials", response_model=ApiResponse[ModelConfigOut])
async def upsert_builtin_credentials(
    config_id: UUID,
    body: ModelBuiltinCredentialsIn,
    ctx: TenantContext = Depends(require_permissions("model:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).upsert_builtin_credentials(config_id, body))


@router.delete("/builtin/{config_id}/credentials", response_model=ApiResponse[ModelConfigOut])
async def delete_builtin_credentials(
    config_id: UUID,
    ctx: TenantContext = Depends(require_permissions("model:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).delete_builtin_credentials(config_id))
