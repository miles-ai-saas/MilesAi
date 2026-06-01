"""提交异步生视频任务（写 generative_jobs + 派发 Celery）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.models.model.generative_job import GenerativeJob, GenerativeJobStatus


async def submit_video_generative_job(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    params: dict,
    source: str,
    source_ref_type: str | None = None,
    source_ref_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> GenerativeJob:
    """创建 PENDING 任务记录；调用方负责 commit 与 Celery dispatch。"""
    job = GenerativeJob(
        tenant_id=ctx.tenant_id,
        kind="video",
        status=GenerativeJobStatus.PENDING,
        source=source,
        source_ref_type=source_ref_type,
        source_ref_id=source_ref_id or agent_id,
        params=params,
        progress_message="排队中",
        progress_percent=0,
        created_by=ctx.user_id,
    )
    db.add(job)
    await db.flush()
    return job


async def submit_image_generative_job(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    params: dict,
    source: str,
    source_ref_type: str | None = None,
    source_ref_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> GenerativeJob:
    """创建 PENDING 生图任务；调用方负责 commit 与 Celery dispatch。"""
    job = GenerativeJob(
        tenant_id=ctx.tenant_id,
        kind="image",
        status=GenerativeJobStatus.PENDING,
        source=source,
        source_ref_type=source_ref_type,
        source_ref_id=source_ref_id or agent_id,
        params=params,
        progress_message="排队中",
        progress_percent=0,
        created_by=ctx.user_id,
    )
    db.add(job)
    await db.flush()
    return job
