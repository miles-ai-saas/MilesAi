"""内置生图 / 生视频 / TTS 工具 handler。

Agent 工具调用链：``invoke_tool_with_context`` → ``handlers.BUILTIN_HANDLERS``
→ 本模块 ``handle_generate_*`` → L1 解析模型 + ``integrations.generative`` 生成引擎。

模型解析优先级：显式 ``model_config_id`` > 智能体绑定模型 > 租户/平台默认。
异步开关：生图/生视频在 ``GenerativeJobService.*_async_enabled()`` 为真时提交 Celery 任务。
TTS 始终同步，产出 WAV 附件。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_common.trace import get_trace_id
from miles_core.tenant import TenantContext
from miles_portal.tenant.generative.services.orchestration import generate_speech_for_model
from miles_portal.tenant.models.services.generative_model_resolve import resolve_tts_model


def _parse_optional_uuid(value: object) -> UUID | None:
    """安全解析可选 UUID，无效值返回 None 而非崩溃。"""
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        # 静默可接受：无效 UUID 视为「未提供」（见 docstring）。
        return None


async def _load_agent_model_context(
    db: AsyncSession,
    agent_id: UUID | None,
) -> tuple[object | None, dict]:
    """加载智能体绑定的 ModelConfig 与 config 字典，供 generative 模型解析复用。"""
    if not agent_id:
        return None, {}
    from miles_core.models.agent import Agent

    agent = await db.get(Agent, agent_id)
    if not agent:
        return None, {}
    agent_config = agent.config if isinstance(agent.config, dict) else {}
    agent_model = None
    if agent.model_config_id:
        from miles_core.models.model import ModelConfig

        agent_model = await db.get(ModelConfig, agent.model_config_id)
    return agent_model, agent_config


async def handle_generate_speech(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID | None,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
) -> dict:
    """TTS 语音合成：text → WAV 附件。

    params: text/prompt, voice, speech_rate, model_config_id（可选）
    返回: attachment_id, mime_type, text_length
    """
    text = str(params.get("text") or params.get("prompt", ""))
    if not text.strip():
        raise BadRequestError("generate_speech 需要 text 参数")

    raw_model = params.get("model_config_id")
    model_uuid = _parse_optional_uuid(raw_model)
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)

    model = await resolve_tts_model(
        db,
        ctx,
        model_config_id=model_uuid,
        agent_model=agent_model,
        agent_config=agent_config,
    )
    return await generate_speech_for_model(
        db,
        ctx,
        model,
        text=text,
        voice=params.get("voice", "longxiaochun"),
        speech_rate=float(params.get("speech_rate", 1.0)),
        agent_id=agent_id,
    )


async def handle_generate_video(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID | None,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
) -> dict:
    """文/图生视频：提交异步任务或同步生成视频附件。

    params: prompt, duration, resolution, image_attachment_id, last_frame_attachment_id,
            model_config_id（可选）
    异步返回 generative_job_id；同步返回 attachment_id。
    """
    from miles_portal.tenant.generative.schemas.job import VideoGenerativeJobCreate
    from miles_portal.tenant.generative.services.job import GenerativeJobService
    from miles_portal.tenant.generative.services.orchestration import generate_video_for_model
    from miles_portal.tenant.models.services.generative_model_resolve import resolve_video_gen_model

    prompt = str(params.get("prompt") or "")
    model_uuid = _parse_optional_uuid(params.get("model_config_id"))
    first_att = _parse_optional_uuid(params.get("image_attachment_id"))
    last_att = _parse_optional_uuid(params.get("last_frame_attachment_id"))
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)

    raw_dur = params.get("duration")
    try:
        duration = int(raw_dur) if raw_dur is not None else 5
    except (TypeError, ValueError):
        duration = 5

    # 用户输入区主动设置的时长优先于 LLM 参数
    preset_dur = agent_config.get("_generative_video_duration")
    if preset_dur is not None:
        try:
            preset_dur = int(preset_dur)
            if preset_dur > 0:
                duration = preset_dur
        except (TypeError, ValueError):
            # 静默可接受：预设时长非正整数即忽略，保留 LLM/默认时长。
            pass

    if GenerativeJobService.video_async_enabled():
        body = VideoGenerativeJobCreate(
            prompt=prompt,
            duration=duration,
            resolution=params.get("resolution"),
            image_attachment_id=first_att,
            last_frame_attachment_id=last_att,
            model_config_id=model_uuid,
        )
        job = await GenerativeJobService(db, ctx).submit_video(
            body,
            source="agent_tool",
            source_ref_type="agent" if agent_id else None,
            source_ref_id=agent_id,
            agent_id=agent_id,
            agent_config=agent_config,
            trace_id=get_trace_id(),
        )
        return {
            "kind": "video",
            "status": "pending",
            "generative_job_id": str(job.id),
            "message": "视频生成任务已提交，通常需 1–5 分钟，请稍候刷新或等待页面自动更新",
        }

    model = await resolve_video_gen_model(
        db,
        ctx,
        model_config_id=model_uuid,
        agent_model=agent_model,
        agent_config=agent_config,
    )
    result = await generate_video_for_model(
        db,
        ctx,
        model,
        prompt=prompt,
        duration=duration,
        resolution=params.get("resolution"),
        image_attachment_id=first_att,
        last_frame_attachment_id=last_att,
        agent_id=agent_id,
    )
    return {
        "kind": "video",
        "attachment_id": str(result.attachment_id),
        "mime_type": result.mime_type,
        "message": "视频已生成",
        "duration_sec": result.duration_sec,
        "media_asset_id": str(result.media_asset_id) if result.media_asset_id else None,
    }


async def handle_generate_image(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID | None,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
) -> dict:
    """文/图生图：提交异步任务或同步生成图片附件。

    params: prompt/description, size, n, image_attachment_id, model_config_id（可选）
    异步返回 generative_job_id；同步返回 attachment_id / attachment_ids。
    """
    from miles_ai.integrations.generative.image.prompt_guard import sanitize_image_prompt
    from miles_ai.integrations.generative.request_prefs import (
        get_request_allow_collage,
        resolve_image_n,
    )
    from miles_portal.tenant.generative.schemas.job import ImageGenerativeJobCreate
    from miles_portal.tenant.generative.services.job import GenerativeJobService
    from miles_portal.tenant.generative.services.orchestration import generate_image_for_model
    from miles_portal.tenant.models.services.generative_model_resolve import resolve_image_gen_model

    prompt = params.get("prompt") or params.get("description") or ""
    model_uuid = _parse_optional_uuid(params.get("model_config_id"))
    image_att = _parse_optional_uuid(params.get("image_attachment_id"))
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)
    n = resolve_image_n(params.get("n"))
    allow_collage = get_request_allow_collage() or bool(agent_config.get("_image_allow_collage"))
    prompt_text = sanitize_image_prompt(str(prompt), allow_collage=allow_collage)
    # 任务参数里带上当轮偏好，Celery worker 无 ContextVar
    job_agent_config = dict(agent_config)
    job_agent_config["_generative_image_n"] = n
    job_agent_config["_image_allow_collage"] = allow_collage

    if GenerativeJobService.image_async_enabled():
        body = ImageGenerativeJobCreate(
            prompt=prompt_text,
            size=params.get("size"),
            n=n,
            image_attachment_id=image_att,
            model_config_id=model_uuid,
        )
        job = await GenerativeJobService(db, ctx).submit_image(
            body,
            source="agent_tool",
            source_ref_type="agent" if agent_id else None,
            source_ref_id=agent_id,
            agent_id=agent_id,
            agent_config=job_agent_config,
            trace_id=get_trace_id(),
        )
        return {
            "kind": "image",
            "status": "pending",
            "generative_job_id": str(job.id),
            "message": "生图任务已提交，完成后将自动展示预览",
        }

    model = await resolve_image_gen_model(
        db,
        ctx,
        model_config_id=model_uuid,
        agent_model=agent_model,
        agent_config=agent_config,
    )
    result = await generate_image_for_model(
        db,
        ctx,
        model,
        prompt=prompt_text,
        size=params.get("size"),
        n=n,
        reference_attachment_id=image_att,
        agent_id=agent_id,
        allow_collage=allow_collage,
    )
    ids = [str(i) for i in result.attachment_ids]
    mids = [str(i) for i in (result.media_asset_ids or [])]
    return {
        "kind": "image",
        "attachment_id": ids[0],
        "attachment_ids": ids,
        "media_asset_id": mids[0] if mids else None,
        "media_asset_ids": mids,
        "mime_type": result.mime_type,
        "message": f"已生成 {len(ids)} 张图片",
    }
