"""租户资源配额只读 API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import get_db, require_permissions
from app.core.tenant import TenantContext
from app.tenant.system.schemas.quota import TenantQuotaOut
from app.tenant.system.services.quota import get_tenant_quota_out

router = APIRouter()


@router.get("", response_model=ApiResponse[TenantQuotaOut])
async def get_system_quota(
    ctx: TenantContext = Depends(require_permissions("system:quota:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantQuotaOut]:
    return ok(await get_tenant_quota_out(db, ctx.tenant_id))
