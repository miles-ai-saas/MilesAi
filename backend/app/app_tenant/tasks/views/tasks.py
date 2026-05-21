from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.models.task import TaskStatus
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.tasks.schemas.task import TaskRecordOut
from app.app_tenant.tasks.services.task import TaskService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> TaskService:
    return TaskService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[TaskRecordOut]])
async def list_tasks(
    status: TaskStatus | None = Query(None),
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("task:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_tasks(params, status=status)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/{task_id}", response_model=ApiResponse[TaskRecordOut])
async def get_task(
    task_id: str,
    ctx: TenantContext = Depends(require_permissions("task:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_task(task_id))


@router.post("/{task_id}/cancel", response_model=ApiResponse[TaskRecordOut])
async def cancel_task(
    task_id: str,
    ctx: TenantContext = Depends(require_permissions("task:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).cancel_task(task_id))


@router.post("/{task_id}/retry", response_model=ApiResponse[TaskRecordOut])
async def retry_task(
    task_id: str,
    ctx: TenantContext = Depends(require_permissions("task:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).retry_task(task_id))
