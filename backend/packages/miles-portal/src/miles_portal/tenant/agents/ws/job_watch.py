"""对话 WebSocket 内推送 generative_job 进度。"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJobStatus
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.ws import protocol as proto
from miles_portal.tenant.generative.schemas.job import GenerativeJobOut
from miles_portal.tenant.generative.services.job import GenerativeJobService
from miles_portal.tenant.generative.services.job_execution import get_generative_job_for_tenant

logger = get_logger(__name__)

_TERMINAL = frozenset(
    {
        GenerativeJobStatus.SUCCESS,
        GenerativeJobStatus.FAILED,
        GenerativeJobStatus.CANCELLED,
    }
)


async def watch_generative_job(ws: WebSocket, ctx: TenantContext, job_id: UUID) -> None:
    """轮询 DB 并推送 generative_job.*，终态后结束。"""
    last_key: tuple | None = None
    idle_ticks = 0
    while idle_ticks < 120:
        try:
            async with AsyncSessionLocal() as db:
                job = await get_generative_job_for_tenant(db, ctx, job_id)
                payload = GenerativeJobOut.model_validate(job).model_dump(mode="json")
                key = (
                    job.status,
                    job.progress_percent,
                    job.progress_message,
                    job.updated_at,
                )
                if key != last_key:
                    last_key = key
                    if job.status == GenerativeJobStatus.PENDING and idle_ticks == 0:
                        await proto.send_json(ws, proto.GENERATIVE_JOB_QUEUED, payload)
                    await proto.send_json(ws, proto.GENERATIVE_JOB_PROGRESS, payload)
                if job.status in _TERMINAL:
                    await proto.send_json(
                        ws,
                        proto.GENERATIVE_JOB_DONE,
                        {
                            "id": str(job.id),
                            "status": job.status.value,
                            "result": payload.get("result"),
                            "error_message": payload.get("error_message"),
                            "job": payload,
                        },
                    )
                    break
                await db.commit()
        except Exception:
            logger.exception("generative job watch failed job_id=%s", job_id)
            break
        idle_ticks += 1
        await asyncio.sleep(1)


def spawn_job_watchers(
    ws: WebSocket,
    ctx: TenantContext,
    job_ids: list[UUID],
    tasks: set[asyncio.Task],
) -> None:
    """为每个任务 ID 创建后台轮询任务，并登记到 ``tasks`` 集合以便统一取消。"""
    for job_id in job_ids:
        task = asyncio.create_task(watch_generative_job(ws, ctx, job_id))
        tasks.add(task)
        task.add_done_callback(tasks.discard)


async def cancel_generative_job_ws(db: AsyncSession, ctx: TenantContext, job_id: UUID) -> GenerativeJobOut:
    """取消生成任务并返回最新任务视图。"""
    svc = GenerativeJobService(db, ctx)
    job = await svc.cancel_job(job_id)
    return GenerativeJobOut.model_validate(job)
