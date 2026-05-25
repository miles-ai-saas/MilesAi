"""租户全局标签 HTTP API。

前缀：``/api/v1/tags``

与 ``sys_categories`` 分离：分类为系统预置单选导航；标签为租户自定义、可多选、跨资源类型共用。
资源侧在创建/更新时传 ``tag_ids``；列表筛选在各资源 API 上传 ``tag_ids`` 查询参数（任一匹配）。
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import get_tenant_context, require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db
from app.tenant.tags.schemas.tag import TenantTagCreate, TenantTagOut
from app.tenant.tags.services.tag import TagService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> TagService:
    return TagService(db, ctx)


@router.get("", response_model=ApiResponse[list[TenantTagOut]])
async def list_tags(
    ctx: TenantContext = Depends(require_permissions("tag:read")),
    db: AsyncSession = Depends(get_db),
):
    """本租户全部标签（按名称排序），供筛选器与 TagPicker 使用。"""
    return ok(await _svc(db, ctx).list_tags())


@router.post("", response_model=ApiResponse[TenantTagOut])
async def create_tag(
    body: TenantTagCreate,
    ctx: TenantContext = Depends(require_permissions("tag:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建标签；slug 由服务端根据 name 生成。"""
    return ok(await _svc(db, ctx).create_tag(body))


@router.delete("/{tag_id}", response_model=ApiResponse[None])
async def delete_tag(
    tag_id: UUID,
    ctx: TenantContext = Depends(require_permissions("tag:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除标签并移除所有实体绑定。"""
    await _svc(db, ctx).delete_tag(tag_id)
    return ok(message="已删除")
