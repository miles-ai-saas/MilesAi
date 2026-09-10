"""
生视频服务入口（``model_type=video_gen``）。

万相 / 豆包：节点内同步轮询至完成（``dashscope_t2v`` / ``volcengine_video``）。
图生视频：服务端读 attachment 字节 → data URL（首帧 / 首尾帧），不向厂商提供 OSS 签名 URL。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.constants import (
    INVOKE_DASHSCOPE_T2V,
    INVOKE_VOLCENGINE_VIDEO,
)
from app.integrations.generative.constants import PURPOSE_CHAT_GENERATED
from app.integrations.generative.persist import persist_generated_bytes
from app.integrations.generative.registry import resolve_invoke_mode
from app.integrations.generative.reference import reference_image_data_url
from app.integrations.generative.types import VideoGenerateResult
from app.integrations.generative.video.providers.dashscope_wan import generate_dashscope_video
from app.integrations.generative.video.providers.volcengine_video import generate_volcengine_video
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType


async def _resolve_frame_data_urls(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    first_attachment_id: UUID | None,
    last_attachment_id: UUID | None,
) -> tuple[str | None, str | None]:
    if last_attachment_id and not first_attachment_id:
        raise BadRequestError("首尾帧生视频需同时提供首帧与尾帧 attachment")

    first_url: str | None = None
    last_url: str | None = None
    if first_attachment_id:
        first_url = await reference_image_data_url(db, ctx, first_attachment_id)
    if last_attachment_id:
        last_url = await reference_image_data_url(db, ctx, last_attachment_id)
    return first_url, last_url


async def generate_video_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    image_attachment_id: UUID | None = None,
    last_frame_attachment_id: UUID | None = None,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
    generative_job_id: UUID | None = None,
    trace_id: str | None = None,
) -> VideoGenerateResult:
    """调用厂商生视频并持久化为 mp4 附件（可能阻塞数分钟）。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("生视频 prompt 不能为空")

    from app.integrations.generative.compliance import check_generative_prompt
    from app.integrations.generative.quota import assert_generative_quota

    prompt = await check_generative_prompt(db, ctx, prompt)

    await assert_generative_quota(db, ctx.tenant_id, units=1)

    first_frame, last_frame = await _resolve_frame_data_urls(
        db,
        ctx,
        first_attachment_id=image_attachment_id,
        last_attachment_id=last_frame_attachment_id,
    )

    progress = None
    if generative_job_id:
        from app.integrations.generative.jobs.progress import GenerativeJobProgress

        progress = GenerativeJobProgress(generative_job_id)
        await progress.update(8, "已提交厂商任务")

    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.VIDEO_GEN.value)
    if mode == INVOKE_DASHSCOPE_T2V:
        video_bytes = await generate_dashscope_video(
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            first_frame_data_url=first_frame,
            last_frame_data_url=last_frame,
            progress=progress,
        )
    elif mode == INVOKE_VOLCENGINE_VIDEO:
        video_bytes = await generate_volcengine_video(
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            first_frame_data_url=first_frame,
            last_frame_data_url=last_frame,
            progress=progress,
        )
    else:
        raise BadRequestError(f"不支持的生视频 invoke_mode: {mode}")

    if progress:
        await progress.update(96, "保存生成物…")

    att_id = await persist_generated_bytes(
        db,
        ctx,
        data=video_bytes,
        filename="generated.mp4",
        mime_type="video/mp4",
        purpose=purpose,
        resource_type="agent" if agent_id else None,
        resource_id=agent_id,
    )
    cover_att_id: UUID | None = None
    from app.integrations.generative.video.cover import extract_video_cover_jpeg

    cover_bytes = extract_video_cover_jpeg(video_bytes)
    if cover_bytes:
        cover_att_id = await persist_generated_bytes(
            db,
            ctx,
            data=cover_bytes,
            filename="generated-cover.jpg",
            mime_type="image/jpeg",
            purpose=purpose,
            resource_type="agent" if agent_id else None,
            resource_id=agent_id,
        )

    from app.tenant.media_assets.services.media_asset import register_media_asset

    row = await register_media_asset(
        db,
        ctx,
        attachment_id=att_id,
        purpose=purpose,
        prompt=prompt,
        model_config_id=model.id,
        kind="video",
        source_ref_type="agent" if agent_id else None,
        source_ref_id=agent_id,
        cover_attachment_id=cover_att_id,
    )
    return VideoGenerateResult(
        attachment_id=att_id,
        mime_type="video/mp4",
        duration_sec=duration,
        media_asset_id=row.id,
    )
