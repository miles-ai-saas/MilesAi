"""租户资源配额只读 API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.deps import get_db, require_permissions
from miles_core.tenant import TenantContext
from miles_portal.tenant.system.schemas.quota import TenantQuotaOut
from miles_portal.tenant.system.services.quota import get_tenant_quota_out

router = APIRouter()


@router.get("", response_model=ApiResponse[TenantQuotaOut])
async def get_system_quota(
    ctx: TenantContext = Depends(require_permissions("system:quota:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantQuotaOut]:
    return ok(await get_tenant_quota_out(db, ctx.tenant_id))
