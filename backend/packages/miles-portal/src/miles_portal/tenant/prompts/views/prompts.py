"""提示词模板 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import get_db
from miles_core.deps import get_page_params, require_permissions
from miles_common.response import ok, page_ok
from miles_core.tenant import TenantContext
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_portal.tenant.prompts.schemas.meta import PromptMetaOut
from miles_portal.tenant.prompts.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
)
from miles_portal.tenant.prompts.services.prompt import PromptService

router = APIRouter()


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[PromptMetaOut])
async def prompts_meta(
    ctx: TenantContext = Depends(require_permissions("prompt:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await PromptService(db, ctx).get_meta())


@router.get("", response_model=ApiResponse[PageResult[PromptTemplateOut]])
async def list_prompts(
    params: PageParams = Depends(get_page_params),
    category_id: UUID | None = Query(None, description="按分类 ID 筛选"),
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    ctx: TenantContext = Depends(require_permissions("prompt:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await PromptService(db, ctx).list_templates(params, category_id=category_id, tag_ids=tag_ids)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[PromptTemplateOut])
async def create_prompt(
    body: PromptTemplateCreate,
    ctx: TenantContext = Depends(require_permissions("prompt:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await PromptService(db, ctx).create_template(body))


@router.patch("/{template_id}", response_model=ApiResponse[PromptTemplateOut])
async def update_prompt(
    template_id: UUID,
    body: PromptTemplateUpdate,
    ctx: TenantContext = Depends(require_permissions("prompt:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await PromptService(db, ctx).update_template(template_id, body))


@router.delete("/{template_id}", response_model=ApiResponse[None])
async def delete_prompt(
    template_id: UUID,
    ctx: TenantContext = Depends(require_permissions("prompt:write")),
    db: AsyncSession = Depends(get_db),
):
    await PromptService(db, ctx).delete_template(template_id)
    return ok(message="已删除")
