"""
TTS 语音合成服务入口（``model_type=tts``）。

与对话/RAG 分离：不走 ``litellm_chat_completion``；结果写入 WAV 附件供播放或流程下游使用。
当前 Provider：DashScope CosyVoice（``INVOKE_DASHSCOPE_TTS``）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.constants import INVOKE_DASHSCOPE_TTS
from app.integrations.generative.constants import PURPOSE_CHAT_GENERATED
from app.integrations.generative.persist import persist_generated_bytes
from app.integrations.generative.registry import resolve_invoke_mode
from app.integrations.generative.tts.providers.dashscope_tts import generate_dashscope_tts
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType


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
    trace_id: str | None = None,
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
