"""工作包看板 API + 阶段推进。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.project import BizWorkPackageKanbanOut, BizWorkPackageOut
from app.biz.services.project import ProjectService
from app.biz.services.work_package import WorkPackageService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _kanban_svc(db: AsyncSession, ctx: TenantContext) -> WorkPackageService:
    return WorkPackageService(db, ctx)


def _project_svc(db: AsyncSession, ctx: TenantContext) -> ProjectService:
    return ProjectService(db, ctx)


@router.get("", response_model=ApiResponse[list[BizWorkPackageKanbanOut]])
async def list_work_packages_kanban(
    project_id: UUID | None = Query(None),
    service_line: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """跨项目工作包列表，供看板使用。"""
    return ok(await _kanban_svc(db, ctx).list_kanban(
        project_id=project_id, service_line=service_line, status=status, limit=limit,
    ))


@router.post("/{wp_id}/advance-stage", response_model=ApiResponse[BizWorkPackageOut])
async def advance_work_package_stage(
    wp_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """推进工作包到服务线模板的下一阶段。"""
    return ok(await _project_svc(db, ctx).advance_work_package_stage(wp_id))


@router.post("/{wp_id}/rollback-stage", response_model=ApiResponse[BizWorkPackageOut])
async def rollback_work_package_stage(
    wp_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """将工作包回退到服务线模板的上一阶段。"""
    return ok(await _project_svc(db, ctx).rollback_work_package_stage(wp_id))
