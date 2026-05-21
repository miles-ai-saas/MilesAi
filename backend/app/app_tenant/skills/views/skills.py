from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.skills.schemas.skill import SkillPackageCreate, SkillPackageOut, SkillPackageUpdate
from app.app_tenant.skills.services.skill import SkillService

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[SkillPackageOut]])
async def list_skills(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("skill:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await SkillService(db, ctx).list_skills(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[SkillPackageOut])
async def create_skill(
    body: SkillPackageCreate,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).create_skill(body))


@router.get("/{skill_id}", response_model=ApiResponse[SkillPackageOut])
async def get_skill(
    skill_id: UUID,
    ctx: TenantContext = Depends(require_permissions("skill:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).get_skill(skill_id))


@router.patch("/{skill_id}", response_model=ApiResponse[SkillPackageOut])
async def update_skill(
    skill_id: UUID,
    body: SkillPackageUpdate,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).update_skill(skill_id, body))


@router.delete("/{skill_id}", response_model=ApiResponse[None])
async def delete_skill(
    skill_id: UUID,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    await SkillService(db, ctx).delete_skill(skill_id)
    return ok(message="已删除")
