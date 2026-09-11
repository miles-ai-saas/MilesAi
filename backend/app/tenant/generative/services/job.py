"""生成任务 API 服务。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.tenant import tenant_filters
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.tenant import TenantContext
from app.integrations.generative.jobs.progress import publish_generative_job_update
from app.tenant.generative.services.job_execution import get_generative_job_for_tenant
from app.integrations.generative.jobs.submit import (
    submit_image_generative_job,
    submit_video_generative_job,
)
from app.models.model.generative_job import GenerativeJob, GenerativeJobStatus
from app.models.task.task_record import CeleryTaskRecord, TaskStatus
from app.tenant.generative.schemas.job import (
    GenerativeJobBatchCancelResult,
    GenerativeJobOut,
    ImageGenerativeJobCreate,
    VideoGenerativeJobCreate,
)
from app.core.jobs.celery_app import celery_app
from app.core.jobs.tasks import RUN_GENERATIVE_IMAGE_JOB, RUN_GENERATIVE_VIDEO_JOB
from app.core.service import BaseService
from app.tenant.tasks.services.task import TaskService

logger = get_logger(__name__)

_TERMINAL = frozenset(
    {
        GenerativeJobStatus.SUCCESS,
        GenerativeJobStatus.FAILED,
        GenerativeJobStatus.CANCELLED,
    }
)

_RETRYABLE = frozenset(
    {
        GenerativeJobStatus.FAILED,
        GenerativeJobStatus.CANCELLED,
    }
)


class GenerativeJobService(BaseService):
    """生成任务应用服务：提交、查询、取消、重试与 SSE 进度推送。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _celery_record_ids_for_jobs(self, job_ids: list[UUID]) -> dict[UUID, UUID]:
        if not job_ids:
            return {}
        stmt = (
            select(CeleryTaskRecord.resource_id, CeleryTaskRecord.id)
            .where(
                CeleryTaskRecord.resource_type == "generative_job",
                CeleryTaskRecord.resource_id.in_(job_ids),
                *tenant_filters(self.ctx, CeleryTaskRecord.tenant_id),
            )
            .order_by(CeleryTaskRecord.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()
        out: dict[UUID, UUID] = {}
        for resource_id, record_id in rows:
            if resource_id and resource_id not in out:
                out[resource_id] = record_id
        return out

    def _job_out(
        self,
        job: GenerativeJob,
        *,
        celery_task_record_id: UUID | None = None,
    ) -> GenerativeJobOut:
        base = GenerativeJobOut.model_validate(job)
        if celery_task_record_id is not None:
            return base.model_copy(update={"celery_task_record_id": celery_task_record_id})
        return base

    async def get_job(self, job_id: UUID) -> GenerativeJobOut:
        """返回任务详情；终态任务顺带回写对话 artifacts（失败静默忽略）。"""
        job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
        # 已结束任务：补写会话 artifacts（修复「任务中心有、会话没有」的历史数据）
        if job.status in _TERMINAL:
            try:
                from app.tenant.agents.services.chat_artifact_sync import sync_job_result_to_chat_messages

                await sync_job_result_to_chat_messages(self.db, job)
                await self.db.flush()
            except Exception:
                # 回写失败不影响任务详情查询
                pass
        record_map = await self._celery_record_ids_for_jobs([job.id])
        return self._job_out(job, celery_task_record_id=record_map.get(job.id))

    async def list_jobs(
        self,
        params: PageParams,
        *,
        status: GenerativeJobStatus | None = None,
        kind: str | None = None,
    ) -> PageResult[GenerativeJobOut]:
        """分页列出任务，可按状态与类型筛选。"""
        filters = list(tenant_filters(self.ctx, GenerativeJob.tenant_id))
        if status is not None:
            filters.append(GenerativeJob.status == status)
        if kind:
            filters.append(GenerativeJob.kind == kind)
        count_stmt = select(func.count(GenerativeJob.id)).where(*filters)
        total = await self.db.scalar(count_stmt) or 0
        stmt = select(GenerativeJob).where(*filters).order_by(GenerativeJob.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        rows = (await self.db.execute(stmt)).scalars().all()
        record_map = await self._celery_record_ids_for_jobs([r.id for r in rows])
        return PageResult(
            items=[self._job_out(r, celery_task_record_id=record_map.get(r.id)) for r in rows],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def _dispatch_job(
        self,
        job: GenerativeJob,
        *,
        celery_task_name: str,
        task_name: str,
    ) -> GenerativeJob:
        # 先 commit 确保 job 已持久化到 DB，再入队 Celery 任务，
        # 避免 Worker 拿到任务时事务未提交导致找不到 job 记录。
        await self.db.commit()
        task = celery_app.send_task(celery_task_name, args=[str(job.id)])
        job.celery_task_id = task.id
        await TaskService(self.db, self.ctx).create_record(
            celery_task_id=task.id,
            task_name=task_name,
            resource_type="generative_job",
            resource_id=job.id,
        )
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def submit_video(
        self,
        body: VideoGenerativeJobCreate,
        *,
        source: str = "api",
        source_ref_type: str | None = None,
        source_ref_id: UUID | None = None,
        agent_id: UUID | None = None,
        agent_config: dict | None = None,
        trace_id: str | None = None,
    ) -> GenerativeJobOut:
        """提交生视频任务：快照参数落库后入队 Celery worker。"""
        params = {
            "prompt": body.prompt.strip(),
            "duration": body.duration or 5,
            "resolution": body.resolution,
            "image_attachment_id": str(body.image_attachment_id) if body.image_attachment_id else None,
            "last_frame_attachment_id": (str(body.last_frame_attachment_id) if body.last_frame_attachment_id else None),
            "model_config_id": str(body.model_config_id) if body.model_config_id else None,
            "agent_id": str(agent_id) if agent_id else None,
            "agent_config": agent_config or {},
            "conversation_id": (agent_config or {}).get("_conversation_id"),
        }
        job = await submit_video_generative_job(
            self.db,
            self.ctx,
            params=params,
            source=source,
            source_ref_type=source_ref_type,
            source_ref_id=source_ref_id,
            agent_id=agent_id,
            trace_id=trace_id,
        )
        await self._dispatch_job(
            job,
            celery_task_name=RUN_GENERATIVE_VIDEO_JOB,
            task_name="run_generative_video_job",
        )
        record_map = await self._celery_record_ids_for_jobs([job.id])
        return self._job_out(job, celery_task_record_id=record_map.get(job.id))

    async def submit_image(
        self,
        body: ImageGenerativeJobCreate,
        *,
        source: str = "api",
        source_ref_type: str | None = None,
        source_ref_id: UUID | None = None,
        agent_id: UUID | None = None,
        agent_config: dict | None = None,
        trace_id: str | None = None,
    ) -> GenerativeJobOut:
        """提交生图任务：快照参数落库后入队 Celery worker。"""
        params = {
            "prompt": body.prompt.strip(),
            "size": body.size,
            "n": body.n or 1,
            "image_attachment_id": str(body.image_attachment_id) if body.image_attachment_id else None,
            "model_config_id": str(body.model_config_id) if body.model_config_id else None,
            "agent_id": str(agent_id) if agent_id else None,
            "agent_config": agent_config or {},
            "conversation_id": (agent_config or {}).get("_conversation_id"),
            "allow_collage": bool((agent_config or {}).get("_image_allow_collage")),
        }
        job = await submit_image_generative_job(
            self.db,
            self.ctx,
            params=params,
            source=source,
            source_ref_type=source_ref_type,
            source_ref_id=source_ref_id,
            agent_id=agent_id,
            trace_id=trace_id,
        )
        await self._dispatch_job(
            job,
            celery_task_name=RUN_GENERATIVE_IMAGE_JOB,
            task_name="run_generative_image_job",
        )
        record_map = await self._celery_record_ids_for_jobs([job.id])
        return self._job_out(job, celery_task_record_id=record_map.get(job.id))

    async def cancel_job(self, job_id: UUID) -> GenerativeJobOut:
        """取消未结束任务：revoke Celery 任务并推送状态；已结束则拒绝。"""
        job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
        if job.status in _TERMINAL:
            raise BadRequestError("任务已结束，无法取消")
        if job.celery_task_id:
            celery_app.control.revoke(job.celery_task_id, terminate=True)
            record = await self.db.scalar(
                select(CeleryTaskRecord).where(
                    CeleryTaskRecord.celery_task_id == job.celery_task_id,
                )
            )
            if record and record.status not in (TaskStatus.SUCCESS, TaskStatus.CANCELLED):
                record.status = TaskStatus.CANCELLED
                record.fail_reason = "用户取消"
        job.status = GenerativeJobStatus.CANCELLED
        job.progress_message = "已取消"
        await self.db.flush()
        await publish_generative_job_update(
            job.tenant_id,
            job_id,
            status=job.status.value,
            message=job.progress_message,
        )
        await self.db.refresh(job)
        record_map = await self._celery_record_ids_for_jobs([job.id])
        return self._job_out(job, celery_task_record_id=record_map.get(job.id))

    async def batch_cancel_jobs(self, job_ids: list[UUID]) -> GenerativeJobBatchCancelResult:
        """批量取消任务，逐项容错；不存在或已结束的 ID 记入 ``skipped``。"""
        cancelled: list[GenerativeJobOut] = []
        skipped: list[str] = []
        for job_id in job_ids:
            try:
                job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
            except NotFoundError:
                skipped.append(str(job_id))
                continue
            if job.status in _TERMINAL:
                skipped.append(str(job_id))
                continue
            if job.celery_task_id:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
                record = await self.db.scalar(
                    select(CeleryTaskRecord).where(
                        CeleryTaskRecord.celery_task_id == job.celery_task_id,
                    )
                )
                if record and record.status not in (TaskStatus.SUCCESS, TaskStatus.CANCELLED):
                    record.status = TaskStatus.CANCELLED
                    record.fail_reason = "用户取消"
            job.status = GenerativeJobStatus.CANCELLED
            job.progress_message = "已取消"
            record_map = await self._celery_record_ids_for_jobs([job.id])
            cancelled.append(self._job_out(job, celery_task_record_id=record_map.get(job.id)))
        if cancelled:
            await self.db.flush()
        return GenerativeJobBatchCancelResult(cancelled=cancelled, skipped=skipped)

    async def retry_job(self, job_id: UUID) -> GenerativeJobOut:
        """重置失败/已取消任务状态，并按 kind 重新入队。"""
        job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
        if job.status not in _RETRYABLE:
            raise BadRequestError("仅失败或已取消的生成任务可重试")

        job.status = GenerativeJobStatus.PENDING
        job.progress_message = "排队中"
        job.progress_percent = 0
        job.result = None
        job.error_message = None

        if job.kind == "video":
            await self._dispatch_job(
                job,
                celery_task_name=RUN_GENERATIVE_VIDEO_JOB,
                task_name="run_generative_video_job",
            )
        elif job.kind == "image":
            await self._dispatch_job(
                job,
                celery_task_name=RUN_GENERATIVE_IMAGE_JOB,
                task_name="run_generative_image_job",
            )
        else:
            raise BadRequestError(f"不支持重试的任务类型: {job.kind}")

        record_map = await self._celery_record_ids_for_jobs([job.id])
        return self._job_out(job, celery_task_record_id=record_map.get(job.id))

    async def stream_job_events(self, job_id: UUID) -> AsyncIterator[str]:
        """SSE：通过 Redis Pub/Sub 推送任务状态/进度，终态后结束。Redis 不可用时自动回退 DB 轮询。"""
        import time

        # 先推送当前状态
        self.db.expire_all()
        job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
        payload = GenerativeJobOut.model_validate(job).model_dump(mode="json")
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        if job.status in _TERMINAL:
            return

        pubsub = None
        channel = None

        try:
            from app.infra.redis import get_redis
            from app.common.redis_keys import RedisKeys

            redis = get_redis()
            channel = RedisKeys.generative_job_progress(str(self.ctx.tenant_id), str(job_id))
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)

            start = time.monotonic()
            terminal_yielded = False
            while time.monotonic() - start < 120:
                msg = await pubsub.get_message(timeout=1.0)
                if msg and msg["type"] == "message":
                    self.db.expire_all()
                    job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
                    payload = GenerativeJobOut.model_validate(job).model_dump(mode="json")
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    if job.status in _TERMINAL:
                        terminal_yielded = True
                        break
            # 兜底：Pub/Sub 超时或消息丢失时，做一次最终 DB 查询避免前端永久等待
            if not terminal_yielded:
                self.db.expire_all()
                job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
                if job.status in _TERMINAL:
                    payload = GenerativeJobOut.model_validate(job).model_dump(mode="json")
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception:
            # Redis 不可用时回退 DB 轮询
            logger.debug("Redis Pub/Sub 不可用，回退 DB 轮询 (job_id=%s)", job_id)
            idle_ticks = 0
            while idle_ticks < 120:
                self.db.expire_all()
                job = await get_generative_job_for_tenant(self.db, self.ctx, job_id)
                payload = GenerativeJobOut.model_validate(job).model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if job.status in _TERMINAL:
                    break
                idle_ticks += 1
                await asyncio.sleep(1)
        finally:
            if pubsub is not None and channel is not None:
                try:
                    await pubsub.unsubscribe(channel)
                except Exception:
                    pass

    @staticmethod
    def video_async_enabled() -> bool:
        """settings 是否开启生视频异步任务。"""
        return bool(get_settings().generative_video_async)

    @staticmethod
    def image_async_enabled() -> bool:
        """settings 是否开启生图异步任务。"""
        return bool(get_settings().generative_image_async)
