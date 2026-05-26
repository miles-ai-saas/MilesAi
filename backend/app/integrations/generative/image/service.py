"""
生图服务入口（``model_type=image_gen``）。

与对话/RAG 分离：不走 ``litellm_chat_completion``；结果写入附件供 ``ChatResponse.artifacts`` 或流程下游使用。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.constants import (
    DEFAULT_IMAGE_SIZE,
    EXTRA_IMAGE_SIZE,
    INVOKE_DASHSCOPE_T2I,
    INVOKE_OPENAI_IMAGES,
    MAX_IMAGES_PER_REQUEST,
)
from app.integrations.generative.image.providers.dashscope_t2i import generate_dashscope_t2i
from app.integrations.generative.image.providers.openai_images import generate_openai_images
from app.integrations.generative.persist import PURPOSE_CHAT_GENERATED, persist_generated_bytes
from app.integrations.generative.model_resolve import pick_default_generative_model
from app.integrations.generative.registry import resolve_invoke_mode
from app.integrations.generative.types import ImageGenerateResult
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType
from app.tenant.models.services.model_resolve import resolve_model_for_invoke


async def _generate_bytes(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int,
) -> list[bytes]:
    """按 invoke_mode 分发到具体 Provider，返回原始图片字节列表。"""
    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.IMAGE_GEN.value)
    if mode == INVOKE_DASHSCOPE_T2I:
        return await generate_dashscope_t2i(model, prompt=prompt, size=size, n=n)
    if mode in (INVOKE_OPENAI_IMAGES, "openai", "dalle"):
        return await generate_openai_images(model, prompt=prompt, size=size, n=n)
    raise BadRequestError(f"不支持的生图 invoke_mode: {mode}")


async def resolve_image_gen_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析生图用 ModelConfig（显式 id > agent 配置 > 智能体绑定模型若为 image_gen）。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_image_model_id"):
        raw_id = UUID(str(cfg["generative_image_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("生图模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.IMAGE_GEN.value:
            raise BadRequestError(f"模型「{row.name}」不是 image_gen 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.IMAGE_GEN.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db,
        model_type=ModelCapabilityType.IMAGE_GEN.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 image_gen 模型，请配置通义万相或其它 image_gen 模型")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)


async def generate_image_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    prompt: str,
    size: str | None = None,
    n: int = 1,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
) -> ImageGenerateResult:
    """调用厂商生图并持久化为附件。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("生图 prompt 不能为空")

    from app.integrations.generative.quota import assert_generative_quota

    extra = model.extra or {}
    resolved_size = size or str(extra.get(EXTRA_IMAGE_SIZE) or DEFAULT_IMAGE_SIZE)
    count = min(max(int(n), 1), MAX_IMAGES_PER_REQUEST)
    await assert_generative_quota(db, ctx.tenant_id, units=count)

    blobs = await _generate_bytes(model, prompt=prompt, size=resolved_size, n=count)
    attachment_ids: list[UUID] = []
    mime = "image/png"
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
        from app.tenant.media_assets.services.media_asset import register_media_asset

        await register_media_asset(
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

    return ImageGenerateResult(attachment_ids=attachment_ids, mime_type=mime)
