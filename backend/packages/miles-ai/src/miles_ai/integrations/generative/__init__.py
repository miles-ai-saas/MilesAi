"""
文生图 / 生视频 / TTS 厂商集成（不走 LiteLLM chat）。

本层只做厂商派发：``image.service.generate_image_bytes`` /
``video.service.generate_video_bytes`` / ``tts.service.generate_tts_bytes``；
不含租户副作用（合规/配额/持久化/媒体资产登记），编排在 L1
``tenant.generative.services.orchestration``，画布节点经
``RunContext.generate_{image,video}_sync`` 注入。
模型解析（``resolve_*_gen_model``）见 L1 ``tenant.models.services.generative_model_resolve``。
"""

from miles_ai.integrations.generative.types import ImageGenerateResult, VideoGenerateResult

__all__ = [
    "ImageGenerateResult",
    "VideoGenerateResult",
]
