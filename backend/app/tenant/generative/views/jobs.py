"""生成任务查询、取消与 SSE 进度流。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageParams, PageResult
from app.core.deps import get_page_params, require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db
from app.models.generative_job import GenerativeJobStatus
from app.tenant.generative.schemas.job import (
    GenerativeJobBatchCancelBody,
    GenerativeJobBatchCancelResult,
    GenerativeJobOut,
    ImageGenerativeJobCreate,
    VideoGenerativeJobCreate,
)
from app.tenant.generative.schemas.meta import GenerativeJobsMetaOut
from app.tenant.generative.services.job import GenerativeJobService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> GenerativeJobService:
    return GenerativeJobService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[GenerativeJobOut]])
async def list_generative_jobs(
    params: PageParams = Depends(get_page_params),
    status: GenerativeJobStatus | None = Query(None),
    kind: str | None = Query(None, description="video 等"),
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_jobs(params, status=status, kind=kind)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/meta", response_model=ApiResponse[GenerativeJobsMetaOut])
async def generative_jobs_meta(
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
):
    from app.tenant.generative.meta import generative_jobs_meta_dict

    return ok(GenerativeJobsMetaOut.model_validate(generative_jobs_meta_dict()))


@router.post("/video", response_model=ApiResponse[GenerativeJobOut])
async def submit_video_job(
    body: VideoGenerativeJobCreate,
    ctx: TenantContext = Depends(require_permissions("attachment:upload")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).submit_video(body, source="api"))


@router.post("/image", response_model=ApiResponse[GenerativeJobOut])
async def submit_image_job(
    body: ImageGenerativeJobCreate,
    ctx: TenantContext = Depends(require_permissions("attachment:upload")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).submit_image(body, source="api"))


@router.post("/batch-cancel", response_model=ApiResponse[GenerativeJobBatchCancelResult])
async def batch_cancel_generative_jobs(
    body: GenerativeJobBatchCancelBody,
    ctx: TenantContext = Depends(require_permissions("attachment:upload")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).batch_cancel_jobs(body.job_ids))


@router.get("/{job_id}/stream")
async def stream_generative_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式推送任务进度（`text/event-stream`）。"""
    gen = _svc(db, ctx).stream_job_events(job_id)

    async def body():
        async for chunk in gen:
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{job_id}/cancel", response_model=ApiResponse[GenerativeJobOut])
async def cancel_generative_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:upload")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).cancel_job(job_id))


@router.post("/{job_id}/retry", response_model=ApiResponse[GenerativeJobOut])
async def retry_generative_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:upload")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).retry_job(job_id))


@router.get("/{job_id}", response_model=ApiResponse[GenerativeJobOut])
async def get_generative_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_job(job_id))
