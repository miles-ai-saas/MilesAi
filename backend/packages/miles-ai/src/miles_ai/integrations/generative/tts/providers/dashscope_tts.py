"""TTS 语音合成 Provider：DashScope CosyVoice REST API。

API: POST /services/aigc/text-to-speech/speech-synthesis
限制：文本最长 1000 字符；需配置 api_key。
返回：WAV 字节 → 上层通过 persist_generated_bytes 持久化为附件。
音色参数：voice（如 longxiaochun）、speech_rate（0.5–2.0）。
"""

from __future__ import annotations

import base64

import httpx

from miles_common.exceptions import AppError, BadRequestError
from miles_ai.integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from miles_core.models.model import ModelConfig


async def generate_dashscope_tts(
    model: ModelConfig,
    *,
    text: str,
    voice: str = "longxiaochun",
    speech_rate: float = 1.0,
) -> bytes:
    """调用 DashScope CosyVoice REST API，返回 WAV 字节。

    API: POST /api/v1/services/aigc/text-to-speech/speech-synthesis
    """
    if not text or not text.strip():
        raise BadRequestError("TTS 文本不能为空")
    if len(text) > 1000:
        raise BadRequestError("TTS 文本最长 1000 字符")

    api_base = (model.api_base or "https://dashscope.aliyuncs.com/api/v1").rstrip("/")
    api_key = model.api_key or ""
    if not api_key:
        raise BadRequestError("TTS 模型未配置 api_key")

    url = f"{api_base}/services/aigc/text-to-speech/speech-synthesis"
    body = {
        "model": model.model_id or "cosyvoice-v1",
        "input": {"text": text.strip()},
        "parameters": {
            "voice": voice,
            "speech_rate": speech_rate,
            "format": "wav",
        },
    }

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        resp = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-DashScope-OssResourceResolve": "enable",
            },
        )
        if resp.status_code >= 400:
            raise AppError(f"DashScope TTS 失败: {resp.text[:300]}", status_code=502)

        data = resp.json()
        output = data.get("output") or data

        audio_url = output.get("audio_url") or output.get("audio") or ""
        if audio_url:
            audio_resp = await client.get(audio_url, timeout=HTTP_DEFAULT_TIMEOUT_SEC)
            if audio_resp.status_code >= 400:
                raise AppError("下载 TTS 音频文件失败", status_code=502)
            return audio_resp.content

        audio_b64 = output.get("audio_data") or output.get("audio_base64") or ""
        if audio_b64:
            return base64.b64decode(audio_b64)

        raise AppError("TTS 响应中未找到音频数据", status_code=502)
