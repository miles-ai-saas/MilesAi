"""Worker 内执行 generative_jobs（asyncio）。"""

from __future__ import annotations

from app.core.logging import get_logger
from uuid import UUID

from app.core.tenant import TenantContext
from app.infra.db import get_worker_session
from app.integrations.generative import (
    generate_image_for_model,
    generate_video_for_model,
    resolve_image_gen_model,
    resolve_video_gen_model,
)
from app.integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from app.integrations.generative.jobs.progress import publish_generative_job_update
from app.integrations.generative.persist import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from app.models.model.generative_job import GenerativeJob, GenerativeJobStatus
from app.models.platform.user import User

logger = get_logger(__name__)


def _optional_uuid(raw) -> UUID | None:
    if not raw:
        return None
    return UUID(str(raw))


async def _sync_chat_after_job(db, job: GenerativeJob) -> None:
    """任务终态写回对话消息，失败不影响主流程。"""
    try:
        from app.tenant.agents.services.chat_artifact_sync import sync_job_result_to_chat_messages

        await sync_job_result_to_chat_messages(db, job)
        await db.commit()
    except Exception:
        logger.exception("sync chat artifacts for generative job %s failed", job.id)


async def run_generative_video_job_async(job_id: UUID) -> None:
    # Celery fork 后父进程的全局 engine 不可复用；用 get_worker_session 创建全新的 engine
    async with get_worker_session() as db:
        job = await db.get(GenerativeJob, job_id)
        if not job:
            raise GenerativeJobNotFound(job_id)
        if job.status == GenerativeJobStatus.CANCELLED:
            return

        user = await db.get(User, job.created_by) if job.created_by else None
        ctx = TenantContext(
            user_id=job.created_by,
            tenant_id=job.tenant_id,
            username=user.username if user else "worker",
            is_superuser=False,
            permissions=frozenset(["attachment:read", "attachment:upload"]),
        )

        job.status = GenerativeJobStatus.RUNNING
        job.progress_message = "生成中"
        job.progress_percent = 5
        await db.commit()
        await publish_generative_job_update(
            job.tenant_id, job_id,
            status=job.status.value,
            percent=job.progress_percent,
            message=job.progress_message,
        )

        params = job.params or {}
        purpose = PURPOSE_FLOW_GENERATED if job.source == "flow_node" else PURPOSE_CHAT_GENERATED
        agent_id = _optional_uuid(params.get("agent_id")) or (job.source_ref_id if job.source_ref_type == "agent" else None)

        try:
            prompt = str(params.get("prompt") or "").strip()
            agent_cfg = params.get("agent_config") if isinstance(params.get("agent_config"), dict) else {}
            duration = int(params.get("duration") or 5)
            preset_dur = agent_cfg.get("_generative_video_duration")
            if preset_dur is not None:
                try:
                    preset_dur = int(preset_dur)
                    if preset_dur > 0:
                        duration = preset_dur
                except (TypeError, ValueError):
                    pass
            model = await resolve_video_gen_model(
                db, ctx,
                model_config_id=_optional_uuid(params.get("model_config_id")),
                agent_config=agent_cfg,
            )
            result = await generate_video_for_model(
                db, ctx, model,
                prompt=prompt,
                duration=duration,
                resolution=params.get("resolution"),
                image_attachment_id=_optional_uuid(params.get("image_attachment_id")),
                last_frame_attachment_id=_optional_uuid(params.get("last_frame_attachment_id")),
                purpose=purpose, agent_id=agent_id, generative_job_id=job_id,
                trace_id=job.trace_id,
            )
            job = await db.get(GenerativeJob, job_id)
            if not job or job.status == GenerativeJobStatus.CANCELLED:
                return
            job.status = GenerativeJobStatus.SUCCESS
            job.progress_message = "已完成"
            job.progress_percent = 100
            job.result = {
                "kind": "video",
                "attachment_id": str(result.attachment_id),
                "mime_type": result.mime_type,
                "duration_sec": result.duration_sec,
                "media_asset_id": str(result.media_asset_id) if result.media_asset_id else None,
            }
            job.error_message = None
            await db.commit()
            await publish_generative_job_update(
                job.tenant_id, job_id,
                status=job.status.value,
                percent=job.progress_percent,
                message=job.progress_message,
            )
            await _sync_chat_after_job(db, job)
        except GenerativeJobCancelled:
            job = await db.get(GenerativeJob, job_id)
            if job and job.status != GenerativeJobStatus.CANCELLED:
                job.status = GenerativeJobStatus.CANCELLED
                job.progress_message = "已取消"
                await db.commit()
                await publish_generative_job_update(
                    job.tenant_id, job_id,
                    status=job.status.value,
                    message=job.progress_message,
                )
                await _sync_chat_after_job(db, job)
        except Exception as exc:
            logger.exception("generative video job %s failed", job_id)
            job = await db.get(GenerativeJob, job_id)
            if job:
                if job.status == GenerativeJobStatus.CANCELLED:
                    return
                job.status = GenerativeJobStatus.FAILED
                job.progress_message = "失败"
                job.error_message = str(exc)[:2000]
                await db.commit()
                await publish_generative_job_update(
                    job.tenant_id, job_id,
                    status=job.status.value,
                    message=job.progress_message,
                )
                await _sync_chat_after_job(db, job)
            raise


async def run_generative_image_job_async(job_id: UUID) -> None:
    # Celery fork 后父进程的全局 engine 不可复用；用 get_worker_session 创建全新的 engine
    async with get_worker_session() as db:
        job = await db.get(GenerativeJob, job_id)
        if not job:
            raise GenerativeJobNotFound(job_id)
        if job.status == GenerativeJobStatus.CANCELLED:
            return

        user = await db.get(User, job.created_by) if job.created_by else None
        ctx = TenantContext(
            user_id=job.created_by,
            tenant_id=job.tenant_id,
            username=user.username if user else "worker",
            is_superuser=False,
            permissions=frozenset(["attachment:read", "attachment:upload"]),
        )

        job.status = GenerativeJobStatus.RUNNING
        job.progress_message = "生图中"
        job.progress_percent = 5
        await db.commit()
        await publish_generative_job_update(
            job.tenant_id, job_id,
            status=job.status.value,
            percent=job.progress_percent,
            message=job.progress_message,
        )

        params = job.params or {}
        purpose = PURPOSE_FLOW_GENERATED if job.source == "flow_node" else PURPOSE_CHAT_GENERATED
        agent_id = _optional_uuid(params.get("agent_id")) or (job.source_ref_id if job.source_ref_type == "agent" else None)

        try:
            prompt = str(params.get("prompt") or "").strip()
            raw_n = params.get("n")
            try:
                n = int(raw_n) if raw_n is not None else 1
            except (TypeError, ValueError):
                n = 1
            # 用户输入区主动设置的 n 始终优先（含 n=1）
            agent_cfg = params.get("agent_config") if isinstance(params.get("agent_config"), dict) else {}
            preset_n = agent_cfg.get("_generative_image_n")
            if preset_n is not None:
                try:
                    n = min(max(int(preset_n), 1), 4)
                except (TypeError, ValueError):
                    pass
            model = await resolve_image_gen_model(
                db, ctx,
                model_config_id=_optional_uuid(params.get("model_config_id")),
                agent_config=params.get("agent_config") if isinstance(params.get("agent_config"), dict) else {},
            )
            result = await generate_image_for_model(
                db, ctx, model,
                prompt=prompt, size=params.get("size"), n=n,
                reference_attachment_id=_optional_uuid(params.get("image_attachment_id")),
                purpose=purpose, agent_id=agent_id, generative_job_id=job_id,
                trace_id=job.trace_id,
            )
            job = await db.get(GenerativeJob, job_id)
            if not job or job.status == GenerativeJobStatus.CANCELLED:
                return
            ids = [str(i) for i in result.attachment_ids]
            mids = [str(i) for i in (result.media_asset_ids or [])]
            logger.info("生成图片任务完成 job_id=%s, attachment_ids=%d, ids=%s", job_id, len(ids), ids)
            job.status = GenerativeJobStatus.SUCCESS
            job.progress_message = "已完成"
            job.progress_percent = 100
            job.result = {
                "kind": "image",
                "attachment_id": ids[0] if ids else None,
                "attachment_ids": ids,
                "media_asset_id": mids[0] if mids else None,
                "media_asset_ids": mids,
                "mime_type": result.mime_type,
            }
            job.error_message = None
            await db.commit()
            await publish_generative_job_update(
                job.tenant_id, job_id,
                status=job.status.value,
                percent=job.progress_percent,
                message=job.progress_message,
            )
            await _sync_chat_after_job(db, job)
        except GenerativeJobCancelled:
            job = await db.get(GenerativeJob, job_id)
            if job and job.status != GenerativeJobStatus.CANCELLED:
                job.status = GenerativeJobStatus.CANCELLED
                job.progress_message = "已取消"
                await db.commit()
                await publish_generative_job_update(
                    job.tenant_id, job_id,
                    status=job.status.value,
                    message=job.progress_message,
                )
                await _sync_chat_after_job(db, job)
        except Exception as exc:
            logger.exception("generative image job %s failed", job_id)
            job = await db.get(GenerativeJob, job_id)
            if job:
                if job.status == GenerativeJobStatus.CANCELLED:
                    return
                job.status = GenerativeJobStatus.FAILED
                job.progress_message = "失败"
                job.error_message = str(exc)[:2000]
                await db.commit()
                await publish_generative_job_update(
                    job.tenant_id, job_id,
                    status=job.status.value,
                    message=job.progress_message,
                )
                await _sync_chat_after_job(db, job)
            raise


async def get_generative_job_for_tenant(
    db,
    ctx: TenantContext,
    job_id: UUID,
) -> GenerativeJob:
    from app.common.exceptions import NotFoundError
    from app.core.tenant import assert_tenant_access

    job = await db.get(GenerativeJob, job_id)
    if not job:
        raise NotFoundError("生成任务不存在")
    assert_tenant_access(ctx, job.tenant_id)
    return job
