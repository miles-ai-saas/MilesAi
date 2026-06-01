"""项目 HTTP API。

提供项目和嵌套工作包的 CRUD 接口：
- GET    /projects          — 分页列表（支持 client_id/status 过滤）
- POST   /projects          — 创建（可同时创建工作包）
- GET    /projects/{id}      — 详情（含工作包列表）
- PATCH  /projects/{id}      — 部分更新
- DELETE /projects/{id}      — 软删除
- GET/POST/PATCH/DELETE /projects/{id}/work-packages  — 工作包子资源
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.project import (
    BizProjectCreate,
    BizProjectOut,
    BizProjectUpdate,
    BizWorkPackageOut,
    BizWorkPackageUpdate,
)
from app.biz.services.project import ProjectService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ProjectService:
    return ProjectService(db, ctx)


# ── projects ──

@router.get("", response_model=ApiResponse[PageResult[BizProjectOut]])
async def list_projects(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    client_id: UUID | None = Query(None),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页查询项目列表，可按客户、状态过滤。"""
    return page_ok(await _svc(db, ctx).list_projects(page=page, size=size, client_id=client_id, status=status))


@router.post("", response_model=ApiResponse[BizProjectOut])
async def create_project(
    body: BizProjectCreate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建项目，可同时创建关联的工作包。"""
    return ok(await _svc(db, ctx).create_project(body))


@router.get("/{project_id}", response_model=ApiResponse[BizProjectOut])
async def get_project(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取项目详情，含完整工作包列表。"""
    return ok(await _svc(db, ctx).get_project(project_id))


@router.patch("/{project_id}", response_model=ApiResponse[BizProjectOut])
async def update_project(
    project_id: UUID,
    body: BizProjectUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """部分更新项目信息。"""
    return ok(await _svc(db, ctx).update_project(project_id, body))


@router.delete("/{project_id}", response_model=ApiResponse[None])
async def delete_project(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """软删除项目（仅标记 deleted_at）。"""
    await _svc(db, ctx).delete_project(project_id)
    return ok(message="已删除")


# ── work packages (nested under project) ──

@router.get("/{project_id}/work-packages", response_model=ApiResponse[list[BizWorkPackageOut]])
async def list_work_packages(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取项目下的所有工作包（按阶段序号排序）。"""
    return ok(await _svc(db, ctx).list_work_packages(project_id))


@router.post("/{project_id}/work-packages", response_model=ApiResponse[BizWorkPackageOut])
async def create_work_package(
    project_id: UUID,
    body: BizWorkPackageUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """在指定项目下创建工作包。"""
    return ok(await _svc(db, ctx).create_work_package(project_id, body))


@router.patch("/{project_id}/work-packages/{wp_id}", response_model=ApiResponse[BizWorkPackageOut])
async def update_work_package(
    project_id: UUID,
    wp_id: UUID,
    body: BizWorkPackageUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新工作包信息（名称、状态、预算等）。"""
    return ok(await _svc(db, ctx).update_work_package(wp_id, body))


@router.delete("/{project_id}/work-packages/{wp_id}", response_model=ApiResponse[None])
async def delete_work_package(
    project_id: UUID,
    wp_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """软删除工作包。"""
    await _svc(db, ctx).delete_work_package(wp_id)
    return ok(message="已删除")
