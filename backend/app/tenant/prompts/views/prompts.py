"""提示词模板 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.prompts.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
)
from app.tenant.prompts.services.prompt import PromptService

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[PromptTemplateOut]])
async def list_prompts(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("prompt:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await PromptService(db, ctx).list_templates(params)
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
