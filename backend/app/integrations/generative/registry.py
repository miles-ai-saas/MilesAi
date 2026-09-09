"""
生成类 ``invoke_mode`` 解析。

``ModelConfig.extra.invoke_mode`` 显式配置优先；否则按 ``vendor`` + ``capability`` 默认：
- image_gen：qwen → dashscope_t2i，doubao → volcengine_image，其它 → openai_images
- video_gen：qwen → dashscope_t2v，doubao → volcengine_video
- tts：默认 dashscope_tts（CosyVoice）

未指定 ``model_config_id`` 时默认模型由 L1 ``tenant.models.services.generative_model_resolve.pick_default_generative_model`` 选取
"""

from app.common.constants.model_extra import EXTRA_INVOKE_MODE
from app.integrations.generative.constants import (
    INVOKE_DASHSCOPE_T2I,
    INVOKE_DASHSCOPE_T2V,
    INVOKE_DASHSCOPE_TTS,
    INVOKE_OPENAI_IMAGES,
    INVOKE_VOLCENGINE_IMAGE,
    INVOKE_VOLCENGINE_VIDEO,
)
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType, ModelVendor


def resolve_invoke_mode(model: ModelConfig, *, capability: str) -> str:
    """返回 ``image_gen`` / ``video_gen`` 等能力对应的 Provider 键名。"""
    extra = model.extra or {}
    explicit = extra.get(EXTRA_INVOKE_MODE) or extra.get("invoke_mode")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if capability == ModelCapabilityType.IMAGE_GEN.value:
        return default_image_invoke_mode(model)
    if capability == ModelCapabilityType.VIDEO_GEN.value:
        return default_video_invoke_mode(model)
    if capability == ModelCapabilityType.TTS.value:
        return default_tts_invoke_mode(model)
    return explicit or ""


def default_image_invoke_mode(model: ModelConfig) -> str:
    """未配置 extra 时的生图默认路由。"""
    if model.vendor == ModelVendor.QWEN.value:
        return INVOKE_DASHSCOPE_T2I
    if model.vendor == ModelVendor.DOUBAO.value:
        return INVOKE_VOLCENGINE_IMAGE
    return INVOKE_OPENAI_IMAGES


def default_video_invoke_mode(model: ModelConfig) -> str:
    """未配置 extra 时的生视频默认路由（万相优先）。"""
    if model.vendor == ModelVendor.QWEN.value:
        return INVOKE_DASHSCOPE_T2V
    if model.vendor == ModelVendor.DOUBAO.value:
        return INVOKE_VOLCENGINE_VIDEO
    return INVOKE_DASHSCOPE_T2V


def default_tts_invoke_mode(model: ModelConfig) -> str:
    """未配置 extra 时的 TTS 默认路由。"""
    return INVOKE_DASHSCOPE_TTS
