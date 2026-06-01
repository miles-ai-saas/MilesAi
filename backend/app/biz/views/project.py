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

from app.biz.schemas.milestone import BizMilestoneCreate, BizMilestoneOut, BizMilestoneUpdate
from app.biz.schemas.project import (
    BizArchiveCaseOut,
    BizArchiveCaseRequest,
    BizClosePreviewOut,
    BizCloseWizardOut,
    BizCloseWizardRequest,
    BizProjectCreate,
    BizProjectMemberCreate,
    BizProjectMemberOut,
    BizProjectOut,
    BizProjectUpdate,
    BizProjectCostSummaryOut,
    BizProjectCloseOut,
    BizWorkPackageCreate,
    BizWorkPackageOut,
    BizWorkPackageUpdate,
)
from app.biz.schemas.project_ai import BizProjectAiContextOut
from app.biz.schemas.supplier import BizProjectSupplierCreate, BizProjectSupplierOut, BizProjectSupplierUpdate
from app.biz.services.milestone import MilestoneService
from app.biz.services.project import ProjectService
from app.biz.services.project_ai import ProjectAiContextService
from app.biz.services.project_archive import ProjectArchiveService
from app.biz.services.project_close import ProjectCloseService
from app.biz.services.supplier import SupplierService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ProjectService:
    return ProjectService(db, ctx)


def _milestone_svc(db: AsyncSession, ctx: TenantContext) -> MilestoneService:
    return MilestoneService(db, ctx)


def _archive_svc(db: AsyncSession, ctx: TenantContext) -> ProjectArchiveService:
    return ProjectArchiveService(db, ctx)


def _close_svc(db: AsyncSession, ctx: TenantContext) -> ProjectCloseService:
    return ProjectCloseService(db, ctx)


def _supplier_svc(db: AsyncSession, ctx: TenantContext) -> SupplierService:
    return SupplierService(db, ctx)


def _ai_svc(db: AsyncSession, ctx: TenantContext) -> ProjectAiContextService:
    return ProjectAiContextService(db, ctx)


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
    """分页查询项目列表，可按客户、状态过滤。"""
    result = await _svc(db, ctx).list_projects(page=page, size=size, client_id=client_id, status=status)
    return page_ok(result.items, result.total, result.page, result.size)


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


@router.get("/{project_id}/cost-summary", response_model=ApiResponse[BizProjectCostSummaryOut])
async def get_cost_summary(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """项目成本汇总：总预算 vs 工作包实际成本。"""
    return ok(await _svc(db, ctx).get_cost_summary(project_id))


@router.get("/{project_id}/close-preview", response_model=ApiResponse[BizClosePreviewOut])
async def get_close_preview(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """结项向导：返回检查清单与可入库交付物。"""
    return ok(await _close_svc(db, ctx).get_close_preview(project_id))


@router.post("/{project_id}/close-wizard", response_model=ApiResponse[BizCloseWizardOut])
async def execute_close_wizard(
    project_id: UUID,
    body: BizCloseWizardRequest,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """结项向导：可选案例入库后结项。"""
    return ok(await _close_svc(db, ctx).execute_close_wizard(project_id, body))


@router.post("/{project_id}/close", response_model=ApiResponse[BizProjectCloseOut])
async def close_project(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """结项：将项目状态置为 closed。"""
    return ok(await _svc(db, ctx).close_project(project_id))


@router.post("/{project_id}/archive-case", response_model=ApiResponse[BizArchiveCaseOut])
async def archive_case(
    project_id: UUID,
    body: BizArchiveCaseRequest,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """将已验收交付物附件沉淀至知识库（涉密客户禁止）。"""
    return ok(await _archive_svc(db, ctx).archive_case(project_id, body))


@router.get("/{project_id}/ai-context", response_model=ApiResponse[BizProjectAiContextOut])
async def get_project_ai_context(
    project_id: UUID,
    work_package_id: UUID | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """项目 AI 上下文：服务线 Agent/Flow 推荐、RAG 策略、结项复盘提示。"""
    return ok(await _ai_svc(db, ctx).get_ai_context(project_id, work_package_id))


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
    body: BizWorkPackageCreate,
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


# ── milestones (nested under work package) ──

@router.get("/{project_id}/work-packages/{wp_id}/milestones", response_model=ApiResponse[list[BizMilestoneOut]])
async def list_milestones(
    project_id: UUID,
    wp_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _milestone_svc(db, ctx).list_milestones(project_id, wp_id))


@router.post("/{project_id}/work-packages/{wp_id}/milestones", response_model=ApiResponse[BizMilestoneOut])
async def create_milestone(
    project_id: UUID,
    wp_id: UUID,
    body: BizMilestoneCreate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _milestone_svc(db, ctx).create(project_id, wp_id, body))


@router.patch("/{project_id}/work-packages/{wp_id}/milestones/{milestone_id}", response_model=ApiResponse[BizMilestoneOut])
async def update_milestone(
    project_id: UUID,
    wp_id: UUID,
    milestone_id: UUID,
    body: BizMilestoneUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _milestone_svc(db, ctx).update(project_id, wp_id, milestone_id, body))


@router.delete("/{project_id}/work-packages/{wp_id}/milestones/{milestone_id}", response_model=ApiResponse[None])
async def delete_milestone(
    project_id: UUID,
    wp_id: UUID,
    milestone_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    await _milestone_svc(db, ctx).delete(project_id, wp_id, milestone_id)
    return ok(message="已删除")


# ── suppliers ──

@router.get("/{project_id}/suppliers", response_model=ApiResponse[list[BizProjectSupplierOut]])
async def list_project_suppliers(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _supplier_svc(db, ctx).list_project_suppliers(project_id))


@router.post("/{project_id}/suppliers", response_model=ApiResponse[BizProjectSupplierOut])
async def add_project_supplier(
    project_id: UUID,
    body: BizProjectSupplierCreate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _supplier_svc(db, ctx).add_project_supplier(project_id, body))


@router.patch("/{project_id}/suppliers/{supplier_id}", response_model=ApiResponse[BizProjectSupplierOut])
async def update_project_supplier(
    project_id: UUID,
    supplier_id: UUID,
    body: BizProjectSupplierUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _supplier_svc(db, ctx).update_project_supplier(project_id, supplier_id, body))


@router.delete("/{project_id}/suppliers/{supplier_id}", response_model=ApiResponse[None])
async def remove_project_supplier(
    project_id: UUID,
    supplier_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    await _supplier_svc(db, ctx).remove_project_supplier(project_id, supplier_id)
    return ok(message="已移除")


# ── members ──

@router.get("/{project_id}/members", response_model=ApiResponse[list[BizProjectMemberOut]])
async def list_members(
    project_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取项目成员列表。"""
    return ok(await _svc(db, ctx).list_members(project_id))


@router.post("/{project_id}/members", response_model=ApiResponse[BizProjectMemberOut])
async def add_member(
    project_id: UUID,
    body: BizProjectMemberCreate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """添加项目成员。"""
    return ok(await _svc(db, ctx).add_member(project_id, body))


@router.delete("/{project_id}/members/{user_id}", response_model=ApiResponse[None])
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """移除项目成员。"""
    await _svc(db, ctx).remove_member(project_id, user_id)
    return ok(message="已移除")
