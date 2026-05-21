from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permissions
from app.common.response import ok
from app.core.tenant import TenantContext
from app.app_tenant.models.schemas.model import ModelConfigCreate, ModelConfigOut, ModelConfigUpdate
from app.app_tenant.models.services.model import ModelService
from app.common.schema import ApiResponse

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ModelService:
    return ModelService(db, ctx)


@router.post("", response_model=ApiResponse[ModelConfigOut])
async def create_model_config(
    body: ModelConfigCreate,
    ctx: TenantContext = Depends(require_permissions("model:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_config(body))


@router.get("", response_model=ApiResponse[list[ModelConfigOut]])
async def list_model_configs(
    ctx: TenantContext = Depends(require_permissions("model:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_configs())


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
