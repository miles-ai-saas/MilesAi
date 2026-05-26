"""Skill 包 HTTP API（前缀 /api/v1/skill-packages）。

路由顺序：/blank、/import/* 须在 /{skill_id} 之前注册，避免路径被 UUID 捕获。
权限：skill:read / skill:write。详见 docs/guides/skill-packages.md。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.skills.schemas.meta import SkillMetaOut
from app.tenant.skills.schemas.skill import (
    SkillFileContent,
    SkillFileNode,
    SkillFileWrite,
    SkillImportGit,
    SkillImportLocal,
    SkillImportResult,
    SkillPackageCreate,
    SkillPackageCreateBlank,
    SkillPackageOut,
    SkillPackageUpdate,
)
from app.tenant.skills.services.import_service import SkillImportService
from app.tenant.skills.services.skill import SkillService

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[SkillPackageOut]])
async def list_skills(
    params: PageParams = Depends(get_page_params),
    category_id: UUID | None = Query(None, description="sys_categories skill 域 ID，工作台 Tab 筛选"),
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    ctx: TenantContext = Depends(require_permissions("skill:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await SkillService(db, ctx).list_skills(
        params, category_id=category_id, tag_ids=tag_ids
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[SkillPackageOut])
async def create_skill(
    body: SkillPackageCreate,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    """遗留创建（工具名 + 片段）；新 UI 请用 POST /blank。"""
    return ok(await SkillService(db, ctx).create_skill(body))


@router.post("/blank", response_model=ApiResponse[SkillPackageOut])
async def create_blank_skill(
    body: SkillPackageCreateBlank,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).create_blank(body))


@router.post("/import/local", response_model=ApiResponse[SkillImportResult])
async def import_local(
    body: SkillImportLocal,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(
        await SkillImportService(db, ctx).import_local(
            body.category_id,
            body.local_path,
            overwrite_existing=body.overwrite_existing,
        )
    )


@router.post("/import/git", response_model=ApiResponse[SkillImportResult])
async def import_git(
    body: SkillImportGit,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(
        await SkillImportService(db, ctx).import_git(
            body.category_id,
            body.repo_url,
            overwrite_existing=body.overwrite_existing,
        )
    )


@router.post("/import/zip", response_model=ApiResponse[SkillImportResult])
async def import_zip(
    category_id: UUID = Query(...),
    overwrite_existing: bool = Query(False),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    """multipart 字段名 file；解压后须含 skills/ 目录。"""
    data = await file.read()
    return ok(
        await SkillImportService(db, ctx).import_zip(
            category_id,
            data,
            file.filename or "upload.zip",
            overwrite_existing=overwrite_existing,
        )
    )


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[SkillMetaOut])
async def skills_meta(
    ctx: TenantContext = Depends(require_permissions("skill:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).get_meta())


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


@router.get("/{skill_id}/files", response_model=ApiResponse[list[SkillFileNode]])
async def list_skill_files(
    skill_id: UUID,
    ctx: TenantContext = Depends(require_permissions("skill:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).list_files(skill_id))


@router.get("/{skill_id}/file", response_model=ApiResponse[SkillFileContent])
async def get_skill_file(
    skill_id: UUID,
    path: str = Query(..., min_length=1, description="技能根下相对路径，如 SKILL.md"),
    ctx: TenantContext = Depends(require_permissions("skill:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).read_file_content(skill_id, path))


@router.put("/{skill_id}/file", response_model=ApiResponse[SkillFileContent])
async def put_skill_file(
    skill_id: UUID,
    body: SkillFileWrite,
    ctx: TenantContext = Depends(require_permissions("skill:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await SkillService(db, ctx).write_file_content(skill_id, body))
