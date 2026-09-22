"""
ModelConfig → LiteLLM 调用封装（L3）。

能力拆分
--------
- **对话**：``litellm_chat_completion`` → ``litellm.acompletion``（llm / reasoning / vision）
- **向量化**：``litellm_embed_texts`` → ``litellm.embedding``（由 ``LiteLLMEmbeddingProvider`` 调用）

``resolve_litellm_model`` 将 vendor/provider 映射为 ``{prefix}/{model_name}``；
租户可在 ``extra.litellm_model`` 覆盖完整 model 字符串。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import (
    DEFAULT_API_BASES,
    ModelCapabilityType,
    ModelVendor,
)
from miles_integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from miles_integrations.litellm.usage_sink import UsageSink

OnDelta = Callable[[str], Awaitable[None]]

# 一期对话链仅支持以下 model_type（与 PRD / model-providers 一致）
CHAT_MODEL_TYPES: frozenset[str] = frozenset(
    {
        ModelCapabilityType.LLM.value,
        ModelCapabilityType.REASONING.value,
        ModelCapabilityType.VISION.value,
    }
)

# vendor → LiteLLM provider 前缀（model 形如 {prefix}/{model_name}）
_VENDOR_LITELLM_PREFIX: dict[str, str] = {
    ModelVendor.DEEPSEEK.value: "deepseek",
    ModelVendor.DOUBAO.value: "volcengine",
    ModelVendor.QWEN.value: "dashscope",
    ModelVendor.OPENAI.value: "openai",
}

# provider 字段兜底（租户自定义可能只填 provider）
_PROVIDER_LITELLM_PREFIX: dict[str, str] = {
    "deepseek": "deepseek",
    "doubao": "volcengine",
    "qwen": "dashscope",
    "openai": "openai",
}


def _ensure_chat_model_type(model: ModelConfig) -> None:
    """校验为 llm / reasoning / vision，embedding 走 integrations.embeddings。"""
    if model.model_type not in CHAT_MODEL_TYPES:
        label = model.model_type or "unknown"
        raise BadRequestError(f"模型「{model.name}」类型为 {label}，当前仅支持对话类（llm / reasoning / vision）")


def resolve_litellm_model(model: ModelConfig) -> str:
    """解析 LiteLLM model 字符串（provider/model_name）。"""
    extra = model.extra or {}
    explicit = extra.get("litellm_model")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    name = (model.model_name or "").strip()
    if not name:
        raise BadRequestError(f"模型「{model.name}」未配置 model_name")

    if "/" in name:
        return name

    prefix = _VENDOR_LITELLM_PREFIX.get(model.vendor) or _PROVIDER_LITELLM_PREFIX.get(model.provider)
    if prefix:
        return f"{prefix}/{name}"

    # 自定义 OpenAI 兼容：走 openai/ + 调用方 api_base
    return f"openai/{name}"


def _resolve_api_base(model: ModelConfig) -> str | None:
    """模型 api_base 或 model_catalog.DEFAULT_API_BASES[vendor]。"""
    if model.api_base:
        return model.api_base.rstrip("/")
    return DEFAULT_API_BASES.get(model.vendor)


def _litellm_error_message(exc: BaseException) -> str:
    msg = getattr(exc, "message", None) or str(exc)
    lower = msg.lower()
    if "authenticationerror" in lower or "incorrect api key" in lower or "invalid api key" in lower:
        return "模型 API Key 鉴权失败，请检查密钥是否正确、未过期，并在「模型供应商」为对应模型配置有效的 DashScope / 厂商密钥"
    return f"模型调用失败: {msg}"


def _import_litellm():
    """延迟导入 litellm，并在首次导入前设置日志级别。"""
    import os

    from miles_core.config import get_settings

    os.environ.setdefault("LITELLM_LOG", get_settings().litellm_log.upper())
    import litellm

    return litellm


def _ensure_messages_valid_for_chat(model: ModelConfig, messages: list[dict[str, Any]]) -> None:
    """对话类模型校验；含 image_url 时仍须为 llm/reasoning/vision。"""
    _ensure_chat_model_type(model)
    from miles_integrations.chat.multimodal import messages_contain_image

    if messages_contain_image(messages) and model.model_type not in CHAT_MODEL_TYPES:
        raise BadRequestError(f"模型「{model.name}」类型为 {model.model_type}，不支持附图对话，请选用 vision 或大语言模型")


def _extract_usage(response: Any) -> tuple[int, int, int]:
    return extract_litellm_usage(response)


def extract_litellm_usage(response: Any) -> tuple[int, int, int]:
    """提取 ``(prompt_tokens, completion_tokens, total_tokens)``；缺失字段补 0，total 缺失时取前两者之和。"""
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return 0, 0, 0
    if isinstance(usage, dict):
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + completion)
        return prompt, completion, total
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or prompt + completion)
    return prompt, completion, total


def _extract_stream_delta_content(chunk: Any) -> str | None:
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return None
    first = choices[0]
    delta = getattr(first, "delta", None)
    if delta is None and isinstance(first, dict):
        delta = first.get("delta")
    if delta is None:
        return None
    content = getattr(delta, "content", None)
    if content is None and isinstance(delta, dict):
        content = delta.get("content")
    if not content:
        return None
    return content if isinstance(content, str) else str(content)


async def litellm_chat_completion_stream(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = HTTP_DEFAULT_TIMEOUT_SEC,
    usage_sink: UsageSink | None = None,
    on_delta: OnDelta | None = None,
) -> str:
    """通过 LiteLLM 发起流式 Chat Completions，可选 on_delta 推送 token。"""
    litellm = _import_litellm()

    _ensure_messages_valid_for_chat(model, messages)

    litellm_model = resolve_litellm_model(model)
    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "stream": True,
    }
    api_key = model.api_key_encrypted
    if api_key:
        kwargs["api_key"] = api_key
    api_base = _resolve_api_base(model)
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = await litellm.acompletion(**kwargs)
    except BadRequestError:
        raise
    except Exception as exc:
        raise AppError(_litellm_error_message(exc), status_code=502) from exc

    parts: list[str] = []
    usage_response: Any | None = None
    async for chunk in response:
        piece = _extract_stream_delta_content(chunk)
        if piece:
            parts.append(piece)
            if on_delta is not None:
                await on_delta(piece)
        usage = getattr(chunk, "usage", None)
        if usage is None and isinstance(chunk, dict):
            usage = chunk.get("usage")
        if usage is not None:
            usage_response = chunk

    if not parts:
        raise AppError("模型返回为空", status_code=502)

    if usage_sink is not None and usage_response is not None:
        prompt_t, completion_t, _ = _extract_usage(usage_response)
        await usage_sink.record(
            prompt_tokens=prompt_t,
            completion_tokens=completion_t,
        )
    return "".join(parts)


async def litellm_chat_completion(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = HTTP_DEFAULT_TIMEOUT_SEC,
    usage_sink: UsageSink | None = None,
) -> str:
    """通过 LiteLLM 发起异步 Chat Completions（content 可为 str 或多模态 part 数组）。"""
    litellm = _import_litellm()

    _ensure_messages_valid_for_chat(model, messages)

    litellm_model = resolve_litellm_model(model)
    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
    }
    api_key = model.api_key_encrypted
    if api_key:
        kwargs["api_key"] = api_key
    api_base = _resolve_api_base(model)
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = await litellm.acompletion(**kwargs)
    except BadRequestError:
        raise
    except Exception as exc:
        raise AppError(_litellm_error_message(exc), status_code=502) from exc

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise AppError("模型返回为空", status_code=502)

    first = choices[0]
    message = getattr(first, "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if content is None and isinstance(first, dict):
        content = (first.get("message") or {}).get("content")
    if content is None:
        raise AppError("模型返回为空", status_code=502)
    if usage_sink is not None:
        prompt_t, completion_t, _ = _extract_usage(response)
        await usage_sink.record(
            prompt_tokens=prompt_t,
            completion_tokens=completion_t,
        )
    return content if isinstance(content, str) else str(content)


def _extract_embedding_vectors(response: Any) -> list[list[float]]:
    """从 LiteLLM embedding 响应提取向量列表。"""
    data = getattr(response, "data", None) or []
    vectors: list[list[float]] = []
    for item in data:
        emb = getattr(item, "embedding", None)
        if emb is None and isinstance(item, dict):
            emb = item.get("embedding")
        if emb is None:
            raise AppError("Embedding 返回为空", status_code=502)
        vectors.append(list(emb))
    return vectors


def litellm_embed_texts(
    texts: list[str],
    *,
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
    timeout: float = HTTP_DEFAULT_TIMEOUT_SEC,
) -> list[list[float]]:
    """同步批量 embedding（供 LangChain Embeddings 与入库任务）。"""
    litellm = _import_litellm()

    if not texts:
        return []

    litellm_model = model.strip()
    if not litellm_model:
        raise BadRequestError("未配置 embedding_litellm_model")

    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "input": texts,
        "timeout": timeout,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base.rstrip("/")

    try:
        response = litellm.embedding(**kwargs)
    except BadRequestError:
        raise
    except Exception as exc:
        raise AppError(f"向量化失败: {getattr(exc, 'message', None) or exc}", status_code=502) from exc

    vectors = _extract_embedding_vectors(response)
    if len(vectors) != len(texts):
        raise AppError("向量化返回条数与输入不一致", status_code=502)
    return vectors
