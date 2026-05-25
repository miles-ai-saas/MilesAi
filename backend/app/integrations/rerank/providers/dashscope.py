"""
DashScope 原生 text-rerank（``invoke_mode=dashscope``）。

请求体格式由 ``rerank_request_format_from_model`` 决定：
- **flat**：顶层 ``query`` + ``documents``（qwen3-rerank 等）
- **nested**：``input`` + ``parameters``（经典 DashScope 结构）

端点见 ``resolve_rerank_endpoint`` 或 ``ModelConfig.api_base``。
"""

from __future__ import annotations

from typing import Any

import httpx

from app.common.exceptions import AppError, BadRequestError
from app.integrations.rerank.constants import (
    DEFAULT_RERANK_INSTRUCT,
    RERANK_REQUEST_FORMAT_FLAT,
    RERANK_REQUEST_FORMAT_NESTED,
)
from app.integrations.rerank.model_meta import (
    rerank_instruct_from_model,
    rerank_request_format_from_model,
    resolve_rerank_endpoint,
)
from app.integrations.rerank.types import RerankHit
from app.models.model import ModelConfig

DEFAULT_TIMEOUT = 120.0


def _build_payload(
    model: ModelConfig,
    *,
    query: str,
    documents: list[str],
    top_n: int | None,
) -> dict[str, Any]:
    """按 flat/nested 格式组装 DashScope 请求体。"""
    model_name = (model.model_name or "").strip()
    if not model_name:
        raise BadRequestError(f"重排模型「{model.name}」未配置 model_name")

    fmt = rerank_request_format_from_model(model)
    if fmt == RERANK_REQUEST_FORMAT_FLAT:
        payload: dict[str, Any] = {
            "model": model_name,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        instruct = rerank_instruct_from_model(model)
        if instruct:
            payload["instruct"] = instruct
        elif model_name.startswith("qwen3-rerank"):
            payload["instruct"] = DEFAULT_RERANK_INSTRUCT
        return payload

    payload = {
        "model": model_name,
        "input": {"query": query, "documents": documents},
        "parameters": {"return_documents": False},
    }
    if top_n is not None:
        payload["parameters"]["top_n"] = top_n
    return payload


def _parse_response(payload: dict[str, Any]) -> list[RerankHit]:
    """解析 output.results 为 index + relevance_score。"""
    if payload.get("code"):
        message = payload.get("message") or payload.get("code")
        raise AppError(f"重排失败: {message}", status_code=502)

    output = payload.get("output") or {}
    results = output.get("results")
    if not isinstance(results, list):
        raise AppError("重排返回为空", status_code=502)

    hits: list[RerankHit] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        score = item.get("relevance_score")
        if not isinstance(index, int) or score is None:
            continue
        hit: RerankHit = {
            "index": index,
            "relevance_score": float(score),
        }
        document = item.get("document")
        if isinstance(document, dict):
            text = document.get("text")
            if isinstance(text, str):
                hit["document"] = text
        elif isinstance(document, str):
            hit["document"] = document
        hits.append(hit)
    return hits


class DashScopeRerankProvider:
    """调用 DashScope text-rerank 端点。"""

    def rerank(
        self,
        model: ModelConfig,
        *,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """POST 重排 API 并返回按相关度排序的命中列表。"""
        if not documents:
            return []

        api_key = model.api_key_encrypted
        if not api_key:
            raise BadRequestError(f"重排模型「{model.name}」未配置 API Key")

        url = resolve_rerank_endpoint(model)
        payload = _build_payload(model, query=query, documents=documents, top_n=top_n)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return _parse_response(response.json())
        except BadRequestError:
            raise
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or str(exc)
            raise AppError(f"重排失败: {detail}", status_code=502) from exc
        except Exception as exc:
            raise AppError(f"重排失败: {exc}", status_code=502) from exc
