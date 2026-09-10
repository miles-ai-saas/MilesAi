"""生成类租户编排（L1）：合规扫描 → 配额 → 参考图 → 厂商派发 → 持久化 → 媒体资产登记。

L3 ``integrations/generative`` 只保留纯厂商派发（``generate_{image,video,tts}_bytes``）；
租户副作用（``ComplianceService`` / ``AttachmentService`` / 附件仓储 / 媒体资产登记）全在本模块；
日配额仅由本模块调用（本模块是**调用点/编排点**），纯额度实现仍在 L3
``tenant.generative.services.quota``（``assert_generative_quota``）。画布同步分支经
``RunContext.generate_{image,video}_sync``（即本模块 ``generate_{image,video}_for_model``）注入执行。
"""

from __future__ import annotations

import base64
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.constants import (
    DEFAULT_IMAGE_SIZE,
    EXTRA_IMAGE_SIZE,
    MAX_IMAGES_PER_REQUEST,
    PURPOSE_CHAT_GENERATED,
)
from app.integrations.generative.image.prompt_guard import sanitize_image_prompt
from app.integrations.generative.image.service import generate_image_bytes
from app.tenant.generative.services.quota import assert_generative_quota
from app.integrations.generative.tts.service import generate_tts_bytes
from app.integrations.generative.types import ImageGenerateResult, VideoGenerateResult
from app.integrations.generative.video.cover import extract_video_cover_jpeg
from app.integrations.generative.video.service import generate_video_bytes
from app.models.compliance.constants import SCAN_MODULE_GENERATIVE
from app.models.model import ModelConfig
from app.tenant.attachments.services.attachment import AttachmentService
from app.tenant.compliance.services.compliance import ComplianceService
from app.tenant.generative.services.persist import persist_generated_bytes
from app.tenant.media_assets.services.media_asset import register_media_asset

logger = logging.getLogger(__name__)


async def check_generative_prompt(
    db: AsyncSession,
    ctx: TenantContext,
    prompt: str,
) -> str:
    """扫描生成 prompt；拦截时抛业务异常，返回脱敏后文本（通常与输入相同）。"""
    compliance = ComplianceService(db, ctx)
    return await compliance.check_input((prompt or "").strip(), module=SCAN_MODULE_GENERATIVE)


async def reference_image_data_url(
    db: AsyncSession,
    ctx: TenantContext,
    attachment_id: UUID,
) -> str:
    """读取租户图片附件并编码为 data URL，供万相/豆包图生图、图生视频使用。"""
    data, mime = await AttachmentService(db, ctx).read_image_bytes(attachment_id)
    encoded = base64.standard_b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


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


async def generate_image_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    prompt: str,
    size: str | None = None,
    n: int = 1,
    reference_attachment_id: UUID | None = None,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
    generative_job_id: UUID | None = None,
    allow_collage: bool = False,
) -> ImageGenerateResult:
    """调用厂商生图并持久化为附件；可选参考图 attachment 实现图生图。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("生图 prompt 不能为空")

    prompt = await check_generative_prompt(db, ctx, prompt)
    prompt = sanitize_image_prompt(prompt, allow_collage=allow_collage)

    ref_url: str | None = None
    if reference_attachment_id:
        ref_url = await reference_image_data_url(db, ctx, reference_attachment_id)

    extra = model.extra or {}
    resolved_size = size or str(extra.get(EXTRA_IMAGE_SIZE) or DEFAULT_IMAGE_SIZE)
    count = min(max(int(n), 1), MAX_IMAGES_PER_REQUEST)
    await assert_generative_quota(db, ctx.tenant_id, units=count)

    job_progress = None
    if generative_job_id:
        from app.integrations.generative.jobs.progress import GenerativeJobProgress

        job_progress = GenerativeJobProgress(generative_job_id)
        await job_progress.update(10, "调用生图 API")

    blobs = await generate_image_bytes(
        model,
        prompt=prompt,
        size=resolved_size,
        n=count,
        reference_image_data_url=ref_url,
        progress=job_progress,
    )
    if job_progress:
        await job_progress.update(80, "保存生成物")

    attachment_ids: list[UUID] = []
    media_asset_ids: list[UUID] = []
    mime = "image/png"
    logger.info("生图 → blobs=%d, n=%d", len(blobs), count)
    for i, data in enumerate(blobs):
        ext = "png"
        if data[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
            ext = "jpg"
        att_id = await persist_generated_bytes(
            db,
            ctx,
            data=data,
            filename=f"generated-{i + 1}.{ext}",
            mime_type=mime,
            purpose=purpose,
            resource_type="agent" if agent_id else None,
            resource_id=agent_id,
        )
        row = await register_media_asset(
            db,
            ctx,
            attachment_id=att_id,
            purpose=purpose,
            prompt=prompt,
            model_config_id=model.id,
            kind="image",
            source_ref_type="agent" if agent_id else None,
            source_ref_id=agent_id,
        )
        attachment_ids.append(att_id)
        media_asset_ids.append(row.id)

    return ImageGenerateResult(attachment_ids=attachment_ids, mime_type=mime, media_asset_ids=media_asset_ids)


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
) -> VideoGenerateResult:
    """调用厂商生视频并持久化为 mp4 附件（可能阻塞数分钟）。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("生视频 prompt 不能为空")

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

    video_bytes = await generate_video_bytes(
        model,
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        first_frame_data_url=first_frame,
        last_frame_data_url=last_frame,
        progress=progress,
    )

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


async def generate_speech_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    text: str,
    voice: str = "longxiaochun",
    speech_rate: float = 1.0,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
) -> dict:
    """调用 TTS 模型生成语音，持久化为附件并返回结果。"""
    audio_bytes = await generate_tts_bytes(
        model,
        text=text,
        voice=voice,
        speech_rate=speech_rate,
    )

    attachment_id = await persist_generated_bytes(
        db,
        ctx,
        data=audio_bytes,
        filename=f"speech-{UUID(int=hash(text) & ((1 << 128) - 1))}.wav",
        mime_type="audio/wav",
        purpose=purpose,
        resource_type="agent" if agent_id else None,
        resource_id=agent_id,
    )

    return {
        "attachment_id": str(attachment_id),
        "mime_type": "audio/wav",
        "text_length": len(text),
    }
