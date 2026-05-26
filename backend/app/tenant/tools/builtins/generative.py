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

    prompt = params.get("prompt") or ""
    raw_model = params.get("model_config_id")
    model_uuid = UUID(str(raw_model)) if raw_model else None
    raw_img = params.get("image_attachment_id")
    image_att = UUID(str(raw_img)) if raw_img else None
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)
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
        prompt=str(prompt),
        duration=int(params.get("duration") or 5),
        resolution=params.get("resolution"),
        image_attachment_id=image_att,
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

    prompt = params.get("prompt") or params.get("description") or ""
    raw_model = params.get("model_config_id")
    model_uuid = UUID(str(raw_model)) if raw_model else None
    agent_model, agent_config = await _load_agent_model_context(db, agent_id)
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
