"""内置生图 / 生视频工具。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext


async def _load_agent_model_context(
    db: AsyncSession,
    agent_id: UUID | None,
) -> tuple[object | None, dict]:
    if not agent_id:
        return None, {}
    from app.models.agent import Agent

    agent = await db.get(Agent, agent_id)
    if not agent:
        return None, {}
    agent_config = agent.config if isinstance(agent.config, dict) else {}
    agent_model = None
    if agent.model_config_id:
        from app.models.model import ModelConfig

        agent_model = await db.get(ModelConfig, agent.model_config_id)
    return agent_model, agent_config


async def handle_generate_video(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID | None,
) -> dict:
    from app.integrations.generative import generate_video_for_model, resolve_video_gen_model
    from app.tenant.generative.schemas.job import VideoGenerativeJobCreate
    from app.tenant.generative.services.job import GenerativeJobService

    prompt = str(params.get("prompt") or "")
    raw_model = params.get("model_config_id")
    model_uuid = UUID(str(raw_model)) if raw_model else None
    raw_first = params.get("image_attachment_id")
    raw_last = params.get("last_frame_attachment_id")
    first_att = UUID(str(raw_first)) if raw_first else None
    last_att = UUID(str(raw_last)) if raw_last else None
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)

    if GenerativeJobService.video_async_enabled():
        body = VideoGenerativeJobCreate(
            prompt=prompt,
            duration=int(params.get("duration") or 5),
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
        duration=int(params.get("duration") or 5),
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
    }


async def handle_generate_image(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID | None,
) -> dict:
    from app.integrations.generative import generate_image_for_model, resolve_image_gen_model
    from app.tenant.generative.schemas.job import ImageGenerativeJobCreate
    from app.tenant.generative.services.job import GenerativeJobService

    prompt = params.get("prompt") or params.get("description") or ""
    raw_model = params.get("model_config_id")
    model_uuid = UUID(str(raw_model)) if raw_model else None
    raw_img = params.get("image_attachment_id")
    image_att = UUID(str(raw_img)) if raw_img else None
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)
    raw_n = params.get("n")
    try:
        n = int(raw_n) if raw_n is not None else 1
    except (TypeError, ValueError):
        n = 1

    if GenerativeJobService.image_async_enabled():
        body = ImageGenerativeJobCreate(
            prompt=str(prompt),
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
            agent_config=agent_config,
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
        prompt=str(prompt),
        size=params.get("size"),
        n=n,
        reference_attachment_id=image_att,
        agent_id=agent_id,
    )
    ids = [str(i) for i in result.attachment_ids]
    return {
        "kind": "image",
        "attachment_id": ids[0],
        "attachment_ids": ids,
        "mime_type": result.mime_type,
        "message": f"已生成 {len(ids)} 张图片",
    }
