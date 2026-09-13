"""统一分类 HTTP API（只读，按 domain）。

前缀：``/api/v1/categories``

租户查询全平台共用的系统预置分类（列表 Tab / 表单单选）。
维护请走运营 ``/api/admin/v1/sys-categories``；用户自定义组织请用 ``/api/v1/tags``。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.deps import get_tenant_context
from miles_core.infra.db import get_db
from miles_core.models.meta.category import CategoryDomain
from miles_core.tenant import TenantContext
from miles_portal.tenant.categories.schemas.category import CategoryOut
from miles_portal.tenant.categories.schemas.meta import CategoryMetaOut
from miles_portal.tenant.categories.services.category import CategoryService

router = APIRouter()

# 按 domain 映射对应模块的 read 权限，避免无 agent 权限的用户拉取 agent 分类
_DOMAIN_READ_PERM: dict[str, str] = {
    CategoryDomain.AGENT.value: "agent:read",
    CategoryDomain.PROMPT.value: "prompt:read",
    CategoryDomain.SKILL.value: "skill:read",
    CategoryDomain.TOOL.value: "tools:read",
}


def _svc(db: AsyncSession, ctx: TenantContext) -> CategoryService:
    return CategoryService(db, ctx)


def _check_domain(domain: str) -> str:
    d = domain.strip().lower()
    if d not in _DOMAIN_READ_PERM:
        raise BadRequestError("domain 须为 agent、prompt、skill 或 tool")
    return d


# GET /categories/meta：domain 枚举字典，须在 /{id} 等路径参数路由之前
@router.get("/meta", response_model=ApiResponse[CategoryMetaOut])
async def categories_meta(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.get("", response_model=ApiResponse[list[CategoryOut]])
async def list_categories(
    domain: str = Query(..., description="agent | prompt | skill | tool"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """返回指定域下的系统预置分类（按 sort_order、name 排序）。"""
    perm = _DOMAIN_READ_PERM[_check_domain(domain)]
    ctx.require_permission(perm)
    return ok(await _svc(db, ctx).list_categories(domain))
