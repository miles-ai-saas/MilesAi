"""从 ModelConfig 解析向量化元数据（维度、invoke_mode、API base）。"""

from __future__ import annotations

from app.common.exceptions import BadRequestError
from app.integrations.embeddings.constants import (
    EXTRA_EMBEDDING_BATCH_SIZE,
    EXTRA_EMBEDDING_DIMENSION,
    EXTRA_INVOKE_MODE,
    INVOKE_MODE_LITELLM,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from app.models.model import ModelConfig
from app.models.model_catalog import DEFAULT_API_BASES, ModelCapabilityType, ModelVendor

# 未显式配置 invoke_mode 时，按 vendor 选择默认后端
_VENDOR_DEFAULT_INVOKE_MODE: dict[str, str] = {
    ModelVendor.QWEN.value: INVOKE_MODE_OPENAI_COMPATIBLE,
}


def embedding_dimension_from_model(model: ModelConfig) -> int:
    extra = model.extra or {}
    dim = extra.get(EXTRA_EMBEDDING_DIMENSION)
    if isinstance(dim, int) and dim > 0:
        return dim
    raise BadRequestError(
        f"向量化模型「{model.name}」未配置 extra.embedding_dimension"
    )


def embedding_batch_size_from_model(model: ModelConfig, *, default: int = 25) -> int:
    extra = model.extra or {}
    size = extra.get(EXTRA_EMBEDDING_BATCH_SIZE)
    if isinstance(size, int) and size > 0:
        return size
    return default


def invoke_mode_from_model(model: ModelConfig) -> str:
    extra = model.extra or {}
    mode = extra.get(EXTRA_INVOKE_MODE)
    if isinstance(mode, str) and mode.strip():
        return mode.strip().lower()
    return _VENDOR_DEFAULT_INVOKE_MODE.get(model.vendor or "", INVOKE_MODE_LITELLM)


def resolve_embedding_api_base(model: ModelConfig) -> str | None:
    if model.api_base:
        return model.api_base.rstrip("/")
    return DEFAULT_API_BASES.get(model.vendor or "")


def ensure_embedding_model_type(model: ModelConfig) -> None:
    if model.model_type != ModelCapabilityType.EMBEDDING.value:
        raise BadRequestError(
            f"模型「{model.name}」类型为 {model.model_type}，知识库须绑定向量化模型（embedding）"
        )
