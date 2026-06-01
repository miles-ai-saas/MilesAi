"""业务中心全局搜索 HTTP API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.search import BizSearchOut
from app.biz.services.search import BizSearchService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


@router.get("", response_model=ApiResponse[BizSearchOut])
async def biz_search(
    q: str = Query("", min_length=0, max_length=128),
    limit: int = Query(12, ge=1, le=30),
    ctx: TenantContext = Depends(require_permissions("biz:dashboard:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await BizSearchService(db, ctx).search(q, limit=limit))
