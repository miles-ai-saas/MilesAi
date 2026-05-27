"""
TTS 语音合成服务入口（``model_type=tts``）。

与对话/RAG 分离：不走 ``litellm_chat_completion``；结果写入 WAV 附件供播放或流程下游使用。
当前 Provider：DashScope CosyVoice（``INVOKE_DASHSCOPE_TTS``）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.constants import INVOKE_DASHSCOPE_TTS
from app.integrations.generative.model_resolve import pick_default_generative_model
from app.integrations.generative.persist import PURPOSE_CHAT_GENERATED, persist_generated_bytes
from app.integrations.generative.registry import resolve_invoke_mode
from app.integrations.generative.tts.providers.dashscope_tts import generate_dashscope_tts
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType
from app.tenant.models.services.model_resolve import resolve_model_for_invoke


async def resolve_tts_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析 TTS 模型：显式 id > agent_model > 租户/平台默认 tts。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_tts_model_id"):
        raw_id = UUID(str(cfg["generative_tts_model_id"]))

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
            raise BadRequestError("TTS 模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.TTS.value:
            raise BadRequestError(f"模型「{row.name}」不是 tts 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.TTS.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db,
        model_type=ModelCapabilityType.TTS.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 tts 模型，请配置语音合成模型（如 DashScope CosyVoice）")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)


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
    source: str = "agent_tool",
) -> dict:
    """调用 TTS 模型生成语音，持久化为附件并返回结果。"""
    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.TTS.value) or INVOKE_DASHSCOPE_TTS

    if mode == INVOKE_DASHSCOPE_TTS:
        audio_bytes = await generate_dashscope_tts(
            model,
            text=text,
            voice=voice,
            speech_rate=speech_rate,
        )
    else:
        raise BadRequestError(f"不支持的 TTS invoke_mode: {mode}")

    attachment = await persist_generated_bytes(
        db,
        ctx,
        audio_bytes,
        filename=f"speech-{UUID(int=hash(text) & ((1 << 128) - 1))}.wav",
        mime_type="audio/wav",
        purpose=purpose,
        agent_id=agent_id,
        source=source,
    )

    return {
        "attachment_id": str(attachment.id),
        "mime_type": "audio/wav",
        "text_length": len(text),
    }
