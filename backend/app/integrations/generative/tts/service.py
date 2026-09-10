"""
TTS 语音合成厂商派发（``model_type=tts``）。

当前 Provider：DashScope CosyVoice（``INVOKE_DASHSCOPE_TTS``）。
租户副作用见 L1 ``tenant.generative.services.orchestration``。
"""

from __future__ import annotations

from app.common.exceptions import BadRequestError
from app.integrations.generative.constants import INVOKE_DASHSCOPE_TTS
from app.integrations.generative.registry import resolve_invoke_mode
from app.integrations.generative.tts.providers.dashscope_tts import generate_dashscope_tts
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType


async def generate_tts_bytes(
    model: ModelConfig,
    *,
    text: str,
    voice: str = "longxiaochun",
    speech_rate: float = 1.0,
) -> bytes:
    """按 invoke_mode 分发到 TTS Provider，返回音频字节。仅厂商派发，无租户副作用。"""
    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.TTS.value) or INVOKE_DASHSCOPE_TTS

    if mode == INVOKE_DASHSCOPE_TTS:
        return await generate_dashscope_tts(
            model,
            text=text,
            voice=voice,
            speech_rate=speech_rate,
        )
    raise BadRequestError(f"不支持的 TTS invoke_mode: {mode}")
