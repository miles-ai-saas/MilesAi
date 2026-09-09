"""
文生图 / 生视频 / TTS 集成（不走 LiteLLM chat）。

- 智能体：``generate_image`` / ``generate_video`` / ``generate_speech`` 内置工具 → ``tenant.tools.invoke``
- 流程画布：``ImageGenerate`` / ``VideoGenerate`` 节点 → ``flow_runtime.nodes.*``
- 厂商：``httpx`` 直调；万相见 ``dashscope_client``；豆包视频见 ``volcengine_client`` / ``volcengine_video``
- TTS：DashScope CosyVoice → ``tts/providers/dashscope_tts``
- 产出物：``persist_generated_bytes`` 写入对象存储；预览走鉴权 ``GET /attachments/{id}/content``，非签名 URL

模型解析（``resolve_image_gen_model`` / ``resolve_video_gen_model`` / ``resolve_tts_model`` /
``pick_default_generative_model``）已上移 L1 ``tenant.models.services.generative_model_resolve``，
本层只暴露接收已解析 ``ModelConfig`` 的生成引擎。
"""

from app.integrations.generative.image.service import generate_image_for_model
from app.integrations.generative.tts.service import generate_speech_for_model
from app.integrations.generative.types import ImageGenerateResult, VideoGenerateResult
from app.integrations.generative.video.service import generate_video_for_model

__all__ = [
    "ImageGenerateResult",
    "VideoGenerateResult",
    "generate_image_for_model",
    "generate_speech_for_model",
    "generate_video_for_model",
]
