"""
OpenAI 兼容 ``POST {api_base}/embeddings``（``invoke_mode=openai_compatible``）。

典型场景
--------
- 阿里云 DashScope compatible-mode
- 自建 vLLM / TEI 等 OpenAI 形状网关

分批
----
``embedding_batch_size_from_model``；通义 DashScope 端点强制单次 input ≤10 条。
请求体带 ``dimensions``，须与 KB 固化维度一致。
"""

from __future__ import annotations

from typing import Any

import httpx

from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig
from miles_integrations.embeddings.model_meta import (
    embedding_batch_size_from_model,
    embedding_dimension_from_model,
    resolve_embedding_api_base,
)
from miles_integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC


def _parse_embedding_response(payload: dict[str, Any], expected: int) -> list[list[float]]:
    """解析 OpenAI 风格 embedding 响应并按 index 排序。"""
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise AppError("Embedding 返回为空", status_code=502)

    if all(isinstance(item, dict) and isinstance(item.get("index"), int) for item in data):
        ordered = sorted(data, key=lambda item: item["index"])
        vectors = [list(item["embedding"]) for item in ordered]
    else:
        vectors = []
        for item in data:
            if not isinstance(item, dict):
                raise AppError("Embedding 返回格式无效", status_code=502)
            embedding = item.get("embedding")
            if embedding is None:
                raise AppError("Embedding 返回为空", status_code=502)
            vectors.append(list(embedding))

    if len(vectors) != expected:
        raise AppError("向量化返回条数与输入不一致", status_code=502)
    return vectors


class OpenAICompatibleEmbeddingProvider:
    """HTTP POST {api_base}/embeddings，支持 dimensions 参数。"""

    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]:
        """分批调用远程 embedding API 并拼接为与 texts 等长的向量列表。"""
        if not texts:
            return []

        model_name = (model.model_name or "").strip()
        if not model_name:
            raise BadRequestError(f"向量化模型「{model.name}」未配置 model_name")

        api_key = model.api_key_encrypted
        if not api_key:
            raise BadRequestError(f"向量化模型「{model.name}」未配置 API Key")

        api_base = resolve_embedding_api_base(model)
        if not api_base:
            raise BadRequestError(f"向量化模型「{model.name}」未配置 api_base")

        dimensions = embedding_dimension_from_model(model)
        batch_size = embedding_batch_size_from_model(model)
        url = f"{api_base.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload: dict[str, Any] = {
                "model": model_name,
                "input": batch,
                "encoding_format": "float",
                "dimensions": dimensions,
            }
            try:
                response = httpx.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=HTTP_DEFAULT_TIMEOUT_SEC,
                )
                response.raise_for_status()
                batch_vectors = _parse_embedding_response(response.json(), len(batch))
            except BadRequestError:
                raise
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text.strip() or str(exc)
                raise AppError(f"向量化失败: {detail}", status_code=502) from exc
            except Exception as exc:
                raise AppError(f"向量化失败: {exc}", status_code=502) from exc
            vectors.extend(batch_vectors)

        return vectors
