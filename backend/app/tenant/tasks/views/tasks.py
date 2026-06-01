"""异步任务 HTTP API：Celery 任务记录查询、取消与重试。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.models.task.task_record import TaskStatus
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.tasks.schemas.meta import TaskMetaOut
from app.tenant.tasks.schemas.task import TaskBatchCancelBody, TaskBatchCancelResult, TaskRecordOut
from app.tenant.tasks.services.task import TaskService

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


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[TaskMetaOut])
async def tasks_meta(
    ctx: TenantContext = Depends(require_permissions("task:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.post("/batch-cancel", response_model=ApiResponse[TaskBatchCancelResult])
async def batch_cancel_tasks(
    body: TaskBatchCancelBody,
    ctx: TenantContext = Depends(require_permissions("task:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).batch_cancel_tasks(body.task_ids))


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
    """仅 document 入库任务：重新 delay ingest_document。"""
    return ok(await _svc(db, ctx).retry_task(task_id))
