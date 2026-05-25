"""从 ModelConfig 解析 rerank 元数据（invoke_mode、端点、请求体格式）。"""

from __future__ import annotations

from app.integrations.rerank.constants import (
    EXTRA_INVOKE_MODE,
    EXTRA_RERANK_INSTRUCT,
    EXTRA_RERANK_REQUEST_FORMAT,
    INVOKE_MODE_DASHSCOPE,
    INVOKE_MODE_OPENAI_COMPATIBLE,
    RERANK_REQUEST_FORMAT_FLAT,
    RERANK_REQUEST_FORMAT_NESTED,
)
from app.models.model import ModelConfig
from app.models.model_catalog import (
    DEFAULT_RERANK_API_ENDPOINTS,
    DEFAULT_RERANK_OPENAI_COMPAT_BASES,
    ModelCapabilityType,
    ModelVendor,
)
from app.common.exceptions import BadRequestError

_VENDOR_DEFAULT_INVOKE_MODE: dict[str, str] = {
    ModelVendor.QWEN.value: INVOKE_MODE_DASHSCOPE,
}

_FLAT_FORMAT_MODELS = frozenset({"qwen3-rerank"})


def invoke_mode_from_model(model: ModelConfig) -> str:
    """解析 provider：dashscope 或 openai_compatible。"""
    extra = model.extra or {}
    mode = extra.get(EXTRA_INVOKE_MODE)
    if isinstance(mode, str) and mode.strip():
        return mode.strip().lower()
    return _VENDOR_DEFAULT_INVOKE_MODE.get(model.vendor or "", INVOKE_MODE_DASHSCOPE)


def rerank_instruct_from_model(model: ModelConfig) -> str | None:
    """可选 rerank 指令（如 qwen3-rerank 的 instruct 字段）。"""
    extra = model.extra or {}
    instruct = extra.get(EXTRA_RERANK_INSTRUCT)
    if isinstance(instruct, str) and instruct.strip():
        return instruct.strip()
    return None


def rerank_request_format_from_model(model: ModelConfig) -> str:
    """DashScope 请求体：flat（顶层 query/documents）或 nested（input/parameters）。"""
    extra = model.extra or {}
    fmt = extra.get(EXTRA_RERANK_REQUEST_FORMAT)
    if isinstance(fmt, str) and fmt.strip():
        return fmt.strip().lower()
    name = (model.model_name or "").strip()
    if name in _FLAT_FORMAT_MODELS or name.startswith("qwen3-rerank"):
        return RERANK_REQUEST_FORMAT_FLAT
    return RERANK_REQUEST_FORMAT_NESTED


def resolve_rerank_endpoint(model: ModelConfig) -> str:
    """DashScope 原生 text-rerank 完整 URL。"""
    if model.api_base:
        return model.api_base.rstrip("/")
    endpoint = DEFAULT_RERANK_API_ENDPOINTS.get(model.vendor or "")
    if endpoint:
        return endpoint
    raise BadRequestError(f"重排模型「{model.name}」未配置 api_base")


def resolve_rerank_openai_compat_base(model: ModelConfig) -> str:
    """OpenAI 兼容 rerank API 的 base（拼接 /reranks）。"""
    if model.api_base:
        return model.api_base.rstrip("/")
    base = DEFAULT_RERANK_OPENAI_COMPAT_BASES.get(model.vendor or "")
    if base:
        return base
    raise BadRequestError(f"重排模型「{model.name}」未配置 api_base")


def ensure_rerank_model_type(model: ModelConfig) -> None:
    """校验模型类型为 rerank。"""
    if model.model_type != ModelCapabilityType.RERANK.value:
        raise BadRequestError(
            f"模型「{model.name}」类型为 {model.model_type}，须为 rerank 重排模型"
        )
