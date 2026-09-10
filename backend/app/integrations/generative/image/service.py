"""
生图厂商派发（``model_type=image_gen``）。

只做 invoke_mode → Provider 分发与参数过滤；租户副作用（合规/配额/持久化/媒体资产
登记）见 L1 ``tenant.generative.services.orchestration``。
"""

from __future__ import annotations

from app.common.exceptions import BadRequestError
from app.integrations.generative.constants import (
    INVOKE_DASHSCOPE_T2I,
    INVOKE_OPENAI_IMAGES,
    INVOKE_VOLCENGINE_IMAGE,
)
from app.integrations.generative.image.providers.dashscope_t2i import generate_dashscope_t2i
from app.integrations.generative.image.providers.openai_images import generate_openai_images
from app.integrations.generative.image.providers.volcengine_image import generate_volcengine_image
from app.integrations.generative.registry import resolve_invoke_mode
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType

# 生图 Provider 注册表：新增 Provider 只需注册即可，无需修改分发逻辑
IMAGE_PROVIDERS = {
    INVOKE_DASHSCOPE_T2I: generate_dashscope_t2i,
    INVOKE_VOLCENGINE_IMAGE: generate_volcengine_image,
    INVOKE_OPENAI_IMAGES: generate_openai_images,
}

IMAGE_PROVIDER_ALIASES: dict[str, str] = {
    "openai": INVOKE_OPENAI_IMAGES,
    "dalle": INVOKE_OPENAI_IMAGES,
}


async def generate_image_bytes(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int,
    reference_image_data_url: str | None = None,
    progress: object | None = None,
) -> list[bytes]:
    """按 invoke_mode 分发到具体 Provider，返回原始图片字节列表。

    按 Provider 函数签名过滤 kwargs，避免各厂商参数名不一致导致 TypeError。
    仅厂商派发，不含租户副作用（合规/配额/持久化）。
    """
    import inspect

    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.IMAGE_GEN.value)
    provider_key = IMAGE_PROVIDER_ALIASES.get(mode, mode)
    provider = IMAGE_PROVIDERS.get(provider_key)
    if not provider:
        raise BadRequestError(f"不支持的生图 invoke_mode: {mode}")

    candidates = {
        "prompt": prompt,
        "size": size,
        "n": n,
        "reference_image_data_url": reference_image_data_url,
        # 兼容旧 Provider 参数名
        "reference_image_url": reference_image_data_url,
        "progress": progress,
    }
    try:
        accepted = set(inspect.signature(provider).parameters)
    except (TypeError, ValueError):
        accepted = set(candidates)
    kwargs = {k: v for k, v in candidates.items() if k in accepted}
    # 同一参考图只传一个参数，避免重复
    if "reference_image_data_url" in kwargs and "reference_image_url" in kwargs:
        del kwargs["reference_image_url"]

    return await provider(model, **kwargs)
