"""部署级基础设施只读 API（L1 .env，租户不可修改）。

/status：组件健康 + 脱敏配置预览；/redis-info、/worker-info 供运维面板扩展指标。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ok
from app.common.schema import ApiResponse
from app.infra.db import get_db
from app.core.deps import require_permissions, require_superuser
from app.core.tenant import TenantContext
from app.tenant.system.schemas.infra import (
    InfraStatusOut,
    InfraTestConnectionIn,
    InfraTestConnectionOut,
)
from app.tenant.system.services.infra import InfraService
from app.utils.health_checks import get_redis_info, get_worker_info

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> InfraService:
    return InfraService(db, ctx)


@router.get("/status", response_model=ApiResponse[InfraStatusOut])
async def get_infra_status(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_status())


@router.post("/test-connection", response_model=ApiResponse[InfraTestConnectionOut])
async def test_infra_connection(
    body: InfraTestConnectionIn | None = None,
    ctx: TenantContext = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    components = body.components if body and body.components else None
    return ok(await _svc(db, ctx).test_connection(components))


@router.get("/redis-info", response_model=ApiResponse[dict])
async def get_redis_cache_info(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
):
    return ok(await get_redis_info())


@router.get("/worker-info", response_model=ApiResponse[dict])
async def get_celery_worker_info(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
):
    return ok(await get_worker_info())
