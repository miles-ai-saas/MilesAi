"""Worker 内执行 generative_jobs（asyncio）。

执行编排用例上移 L1（原 ``integrations/generative/jobs/runner.py``）：
worker 进程内取 job → 合成最小 TenantContext → 解析模型 → 调用 L3 生成引擎 → 落库/推送进度。
供 ``workers/tasks/generative.py``（Celery 任务）与 ``tenant.generative.services.job`` 查询复用。
画布异步提交回调亦在本模块装配（``RunContext.submit_generative_*``）。
"""

from __future__ import annotations

from uuid import UUID

from miles_ai.integrations.generative.constants import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from miles_ai.integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from miles_ai.integrations.generative.jobs.progress import publish_generative_job_update
from miles_common.trace import get_trace_id
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob, GenerativeJobStatus
from miles_core.models.platform.user import User
from miles_core.tenant import TenantContext
from miles_portal.tenant.generative.services.orchestration import generate_image_for_model, generate_video_for_model
from miles_portal.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)

logger = get_logger(__name__)


def _optional_uuid(raw) -> UUID | None:
    if not raw:
        return None
    return UUID(str(raw))


async def _sync_chat_after_job(db, job: GenerativeJob) -> None:
    """任务终态写回对话消息，失败不影响主流程。"""
    try:
        from miles_portal.tenant.agents.services.chat_artifact_sync import sync_job_result_to_chat_messages

        await sync_job_result_to_chat_messages(db, job)
        await db.commit()
    except Exception:
        logger.exception("sync chat artifacts for generative job %s failed", job.id)


async def _publish_state(db, job: GenerativeJob, job_id: UUID, *, percent: int | None) -> None:
    """提交当前 job 状态并推送一次进度通知。

    ``percent`` 必填：终态取消/失败本就不公布进度，须显式传 ``None``；若一律读回
    ``job.progress_percent``，会把停留的旧值（如运行中的 5）当终态进度推给前端。
    """
    await db.commit()
    await publish_generative_job_update(
        job.tenant_id,
        job_id,
        status=job.status.value,
        percent=percent,
        message=job.progress_message,
    )


async def _publish_state_and_sync(db, job: GenerativeJob, job_id: UUID, *, percent: int | None) -> None:
    """推送终态后，再把结果写回对话消息。"""
    await _publish_state(db, job, job_id, percent=percent)
    await _sync_chat_after_job(db, job)


async def _worker_context(db, job: GenerativeJob) -> TenantContext:
    """按 job 创建者合成 worker 侧最小 TenantContext；查不到用户时回退 worker 身份。"""
    user = await db.get(User, job.created_by) if job.created_by else None
    return TenantContext(
        user_id=job.created_by,
        tenant_id=job.tenant_id,
        username=user.username if user else "worker",
        is_superuser=False,
        permissions=frozenset(["attachment:read", "attachment:upload"]),
    )


async def _finalize_cancelled(db, job_id: UUID) -> None:
    """用户取消：把尚未标记取消的任务落到 CANCELLED 并推送。"""
    job = await db.get(GenerativeJob, job_id)
    if job and job.status != GenerativeJobStatus.CANCELLED:
        job.status = GenerativeJobStatus.CANCELLED
        job.progress_message = "已取消"
        await _publish_state_and_sync(db, job, job_id, percent=None)


async def _finalize_failed(db, job_id: UUID, exc: Exception) -> None:
    """生成失败：把任务落到 FAILED 并推送。

    唯一不改终态的情形是任务在生成期间已被用户取消——此时不覆盖 CANCELLED、也不推
    失败通知。**但调用方仍须把异常向上抛**：曾因「已取消就静默返回」，异常只在
    worker 日志里留痕，Celery 任务却上报成功，任务实际停在 CANCELLED，失败被完全吞掉。
    """
    job = await db.get(GenerativeJob, job_id)
    if job is None or job.status == GenerativeJobStatus.CANCELLED:
        return
    job.status = GenerativeJobStatus.FAILED
    job.progress_message = "失败"
    job.error_message = str(exc)[:2000]
    await _publish_state_and_sync(db, job, job_id, percent=None)


def _preset_positive_duration(agent_cfg: dict) -> int | None:
    """``agent_config._generative_video_duration`` 预设时长；非正整数或不可解析视为未设。"""
    raw = agent_cfg.get("_generative_video_duration")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        # 静默可接受：预设时长非正整数或不可解析，即「未设置」（见 docstring）。
        return None
    return value if value > 0 else None


async def run_generative_video_job_async(job_id: UUID) -> None:
    """Worker 内执行生视频任务：置运行中 → 生成 → 落库并推送终态。"""
    # engine 按事件循环持有（见 infra/db/async_session），直接取 AsyncSessionLocal() 即与当前 loop 对齐
    async with AsyncSessionLocal() as db:
        job = await db.get(GenerativeJob, job_id)
        if not job:
            raise GenerativeJobNotFound(job_id)
        if job.status == GenerativeJobStatus.CANCELLED:
            return

        ctx = await _worker_context(db, job)

        job.status = GenerativeJobStatus.RUNNING
        job.progress_message = "生成中"
        job.progress_percent = 5
        await _publish_state(db, job, job_id, percent=job.progress_percent)

        params = job.params or {}
        purpose = PURPOSE_FLOW_GENERATED if job.source == "flow_node" else PURPOSE_CHAT_GENERATED
        agent_id = _optional_uuid(params.get("agent_id")) or (job.source_ref_id if job.source_ref_type == "agent" else None)

        try:
            prompt = str(params.get("prompt") or "").strip()
            agent_cfg = params.get("agent_config") if isinstance(params.get("agent_config"), dict) else {}
            duration = int(params.get("duration") or 5)
            preset_dur = _preset_positive_duration(agent_cfg)
            if preset_dur is not None:
                duration = preset_dur
            model = await resolve_video_gen_model(
                db,
                ctx,
                model_config_id=_optional_uuid(params.get("model_config_id")),
                agent_config=agent_cfg,
            )
            result = await generate_video_for_model(
                db,
                ctx,
                model,
                prompt=prompt,
                duration=duration,
                resolution=params.get("resolution"),
                image_attachment_id=_optional_uuid(params.get("image_attachment_id")),
                last_frame_attachment_id=_optional_uuid(params.get("last_frame_attachment_id")),
                purpose=purpose,
                agent_id=agent_id,
                generative_job_id=job_id,
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
            await _publish_state_and_sync(db, job, job_id, percent=job.progress_percent)
        except GenerativeJobCancelled:
            await _finalize_cancelled(db, job_id)
        except Exception as exc:
            # 不带堆栈：原样重抛后经 `_run_generative_task` 由 Celery 记录完整堆栈，
            # 此处只留可 grep 的 job_id 与原因，否则同一堆栈会打三份。
            logger.error("generative video job %s failed: %s", job_id, exc)
            await _finalize_failed(db, job_id, exc)
            raise


async def run_generative_image_job_async(job_id: UUID) -> None:
    """Worker 内执行生图任务：置运行中 → 生成 → 落库并推送终态。"""
    # engine 按事件循环持有（见 infra/db/async_session），直接取 AsyncSessionLocal() 即与当前 loop 对齐
    async with AsyncSessionLocal() as db:
        job = await db.get(GenerativeJob, job_id)
        if not job:
            raise GenerativeJobNotFound(job_id)
        if job.status == GenerativeJobStatus.CANCELLED:
            return

        ctx = await _worker_context(db, job)

        job.status = GenerativeJobStatus.RUNNING
        job.progress_message = "生图中"
        job.progress_percent = 5
        await _publish_state(db, job, job_id, percent=job.progress_percent)

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
                    # 静默可接受：用户输入区预设张数非正整数即「未设置」，保留 LLM/默认值。
                    pass
            model = await resolve_image_gen_model(
                db,
                ctx,
                model_config_id=_optional_uuid(params.get("model_config_id")),
                agent_config=params.get("agent_config") if isinstance(params.get("agent_config"), dict) else {},
            )
            result = await generate_image_for_model(
                db,
                ctx,
                model,
                prompt=prompt,
                size=params.get("size"),
                n=n,
                reference_attachment_id=_optional_uuid(params.get("image_attachment_id")),
                purpose=purpose,
                agent_id=agent_id,
                generative_job_id=job_id,
                allow_collage=bool(params.get("allow_collage") or agent_cfg.get("_image_allow_collage")),
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
            await _publish_state_and_sync(db, job, job_id, percent=job.progress_percent)
        except GenerativeJobCancelled:
            await _finalize_cancelled(db, job_id)
        except Exception as exc:
            # 不带堆栈：同生视频路径 —— 堆栈由 Celery 记录，此处只留上下文。
            logger.error("generative image job %s failed: %s", job_id, exc)
            await _finalize_failed(db, job_id, exc)
            raise


async def get_generative_job_for_tenant(
    db,
    ctx: TenantContext,
    job_id: UUID,
) -> GenerativeJob:
    """按租户校验后加载生成任务；不存在或越权抛错。"""
    from miles_common.exceptions import NotFoundError
    from miles_core.tenant import assert_tenant_access

    job = await db.get(GenerativeJob, job_id)
    if not job:
        raise NotFoundError("生成任务不存在")
    assert_tenant_access(ctx, job.tenant_id)
    return job


async def submit_generative_image_job(
    db,
    tenant_ctx: TenantContext,
    *,
    prompt: str,
    size: str | None,
    n: int,
    image_attachment_id: UUID | None,
    model_config_id: UUID,
    agent_id: UUID | None,
    agent_config: dict | None = None,
) -> UUID:
    """画布 ImageGenerate 异步分支提交回调（L1 装配注入 RunContext）。

    函数级 import ``GenerativeJobService`` 避免 ``services.job`` 顶层循环依赖；
    仅构造 JobCreate 并提交，会话提交（``db.commit``）由节点统一执行。
    """
    from miles_portal.tenant.generative.schemas.job import ImageGenerativeJobCreate
    from miles_portal.tenant.generative.services.job import GenerativeJobService

    body = ImageGenerativeJobCreate(
        prompt=prompt,
        size=size,
        n=n,
        image_attachment_id=image_attachment_id,
        model_config_id=model_config_id,
    )
    out = await GenerativeJobService(db, tenant_ctx).submit_image(
        body,
        source="flow_node",
        agent_id=agent_id,
        agent_config=agent_config or {},
        trace_id=get_trace_id(),
    )
    return out.id


async def submit_generative_video_job(
    db,
    tenant_ctx: TenantContext,
    *,
    prompt: str,
    duration: int,
    resolution: str | None,
    image_attachment_id: UUID | None,
    last_frame_attachment_id: UUID | None,
    model_config_id: UUID | None,
    agent_id: UUID | None,
    agent_config: dict | None = None,
) -> UUID:
    """画布 VideoGenerate 异步分支提交回调（L1 装配注入 RunContext）。"""
    from miles_portal.tenant.generative.schemas.job import VideoGenerativeJobCreate
    from miles_portal.tenant.generative.services.job import GenerativeJobService

    body = VideoGenerativeJobCreate(
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        image_attachment_id=image_attachment_id,
        last_frame_attachment_id=last_frame_attachment_id,
        model_config_id=model_config_id,
    )
    out = await GenerativeJobService(db, tenant_ctx).submit_video(
        body,
        source="flow_node",
        agent_id=agent_id,
        agent_config=agent_config or {},
        trace_id=get_trace_id(),
    )
    return out.id
