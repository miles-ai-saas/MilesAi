from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.hooks.schemas.hook import HookDefinitionCreate, HookDefinitionOut
from app.app_tenant.hooks.services.hook import HookService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> HookService:
    return HookService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[HookDefinitionOut]])
async def list_hooks(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("hook:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_hooks(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[HookDefinitionOut])
async def create_hook(
    body: HookDefinitionCreate,
    ctx: TenantContext = Depends(require_permissions("hook:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_hook(body))
