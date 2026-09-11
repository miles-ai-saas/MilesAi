"""
生视频厂商派发（``model_type=video_gen``）。

万相 / 豆包：节点内同步轮询至完成；``invoke_mode`` 取值 ``dashscope_t2v``（派发到模块
``dashscope_wan``）/ ``volcengine_video``。
只做 invoke_mode 分发；租户副作用见 L1 ``tenant.generative.services.orchestration``。
"""

from __future__ import annotations

from miles_common.exceptions import BadRequestError
from miles_ai.integrations.generative.constants import (
    INVOKE_DASHSCOPE_T2V,
    INVOKE_VOLCENGINE_VIDEO,
)
from miles_ai.integrations.generative.registry import resolve_invoke_mode
from miles_ai.integrations.generative.video.providers.dashscope_wan import generate_dashscope_video
from miles_ai.integrations.generative.video.providers.volcengine_video import generate_volcengine_video
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType


async def generate_video_bytes(
    model: ModelConfig,
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    first_frame_data_url: str | None = None,
    last_frame_data_url: str | None = None,
    progress: object | None = None,
) -> bytes:
    """按 invoke_mode 分发到具体厂商，返回 mp4 字节（节点内同步轮询至完成）。

    仅厂商派发，不含租户副作用（合规/配额/持久化）。
    """
    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.VIDEO_GEN.value)
    if mode == INVOKE_DASHSCOPE_T2V:
        return await generate_dashscope_video(
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            first_frame_data_url=first_frame_data_url,
            last_frame_data_url=last_frame_data_url,
            progress=progress,
        )
    if mode == INVOKE_VOLCENGINE_VIDEO:
        return await generate_volcengine_video(
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            first_frame_data_url=first_frame_data_url,
            last_frame_data_url=last_frame_data_url,
            progress=progress,
        )
    raise BadRequestError(f"不支持的生视频 invoke_mode: {mode}")
