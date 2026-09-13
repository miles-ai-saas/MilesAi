"""
从 ModelConfig 解析向量化元数据。

关键字段（``ModelConfig.extra``）
--------------------------------
- ``embedding_dimension``：创建 KB 时写入 ``KnowledgeBase.embedding_dimension``
- ``invoke_mode``：registry 分发键（local / openai_compatible / litellm）
- ``embedding_batch_size``：单次 API 条数；通义 DashScope 强制 ≤10

未配置 ``invoke_mode`` 时按 ``vendor`` 默认（如 Qwen → openai_compatible）。
"""

from __future__ import annotations

from miles_ai.integrations.embeddings.constants import (
    DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX,
    EXTRA_EMBEDDING_BATCH_SIZE,
    EXTRA_EMBEDDING_DIMENSION,
    INVOKE_MODE_LITELLM,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from miles_common.constants.model_extra import EXTRA_INVOKE_MODE
from miles_common.exceptions import BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import DEFAULT_API_BASES, ModelCapabilityType, ModelVendor

# 未显式配置 invoke_mode 时，按 vendor 选择默认后端
_VENDOR_DEFAULT_INVOKE_MODE: dict[str, str] = {
    ModelVendor.QWEN.value: INVOKE_MODE_OPENAI_COMPATIBLE,
}

_VENDOR_DEFAULT_EMBEDDING_BATCH_SIZE: dict[str, int] = {
    ModelVendor.QWEN.value: DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX,
}


def _is_dashscope_embedding_endpoint(model: ModelConfig) -> bool:
    """判断是否走 DashScope 兼容端点（需限制 batch≤10）。"""
    base = (model.api_base or DEFAULT_API_BASES.get(model.vendor or "") or "").lower()
    return "dashscope.aliyuncs.com" in base


def embedding_dimension_from_model(model: ModelConfig) -> int:
    """从 ModelConfig.extra.embedding_dimension 读取向量维度。"""
    extra = model.extra or {}
    dim = extra.get(EXTRA_EMBEDDING_DIMENSION)
    if isinstance(dim, int) and dim > 0:
        return dim
    raise BadRequestError(f"向量化模型「{model.name}」未配置 extra.embedding_dimension")


def embedding_batch_size_from_model(model: ModelConfig, *, default: int = 25) -> int:
    """解析单次 /embeddings 请求的 input 条数上限；通义强制≤10。"""
    extra = model.extra or {}
    size = extra.get(EXTRA_EMBEDDING_BATCH_SIZE)
    if isinstance(size, int) and size > 0:
        resolved = size
    else:
        resolved = _VENDOR_DEFAULT_EMBEDDING_BATCH_SIZE.get(model.vendor or "", default)
    if model.vendor == ModelVendor.QWEN.value or _is_dashscope_embedding_endpoint(model):
        resolved = min(resolved, DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX)
    return resolved


def invoke_mode_from_model(model: ModelConfig) -> str:
    """解析 provider 分发键：local / openai_compatible / litellm。"""
    extra = model.extra or {}
    mode = extra.get(EXTRA_INVOKE_MODE)
    if isinstance(mode, str) and mode.strip():
        return mode.strip().lower()
    return _VENDOR_DEFAULT_INVOKE_MODE.get(model.vendor or "", INVOKE_MODE_LITELLM)


def resolve_embedding_api_base(model: ModelConfig) -> str | None:
    """模型自定义 api_base 或 vendor 默认 base。"""
    if model.api_base:
        return model.api_base.rstrip("/")
    return DEFAULT_API_BASES.get(model.vendor or "")


def ensure_embedding_model_type(model: ModelConfig) -> None:
    """校验模型类型为 embedding，避免 KB 绑定 chat 模型。"""
    if model.model_type != ModelCapabilityType.EMBEDDING.value:
        raise BadRequestError(f"模型「{model.name}」类型为 {model.model_type}，知识库须绑定向量化模型（embedding）")
