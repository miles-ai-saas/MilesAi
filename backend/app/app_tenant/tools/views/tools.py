from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.tools.schemas.tools import ToolCreate, ToolOut
from app.app_tenant.tools.services.tools import ToolsService

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[ToolOut]])
async def list_tools(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await ToolsService(db, ctx).list_tools(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[ToolOut])
async def create_tool(
    body: ToolCreate,
    ctx: TenantContext = Depends(require_permissions("tools:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await ToolsService(db, ctx).create_tool(body))


@router.get("/builtin", response_model=ApiResponse[list[dict]])
async def list_builtin(
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await ToolsService(db, ctx).list_builtin())
