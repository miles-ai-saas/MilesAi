"""
OpenAI 兼容 Rerank API（``invoke_mode=openai_compatible``）。

``POST {api_base}/reranks``，请求体含 ``model``、``query``、``documents``、可选 ``top_n`` / ``instruct``。
解析 ``results`` 或 ``data`` 数组中的 ``index`` + ``relevance_score``。
"""

from __future__ import annotations

from typing import Any

import httpx

from app.common.exceptions import AppError, BadRequestError
from app.integrations.rerank.constants import DEFAULT_RERANK_INSTRUCT
from app.integrations.rerank.model_meta import (
    rerank_instruct_from_model,
    resolve_rerank_openai_compat_base,
)
from app.integrations.rerank.types import RerankHit
from app.models.model import ModelConfig

DEFAULT_TIMEOUT = 120.0


def _parse_response(payload: dict[str, Any]) -> list[RerankHit]:
    """解析 results/data 数组。"""
    results = payload.get("results") or payload.get("data")
    if not isinstance(results, list):
        raise AppError("重排返回为空", status_code=502)

    hits: list[RerankHit] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if not isinstance(index, int) or score is None:
            continue
        hit: RerankHit = {
            "index": index,
            "relevance_score": float(score),
        }
        document = item.get("document")
        if isinstance(document, str):
            hit["document"] = document
        hits.append(hit)
    return hits


class OpenAICompatibleRerankProvider:
    """POST {base}/reranks，请求体与 OpenAI Rerank 对齐。"""

    def rerank(
        self,
        model: ModelConfig,
        *,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """对 documents 重排并返回 top_n 条 RerankHit。"""
        if not documents:
            return []

        model_name = (model.model_name or "").strip()
        if not model_name:
            raise BadRequestError(f"重排模型「{model.name}」未配置 model_name")

        api_key = model.api_key_encrypted
        if not api_key:
            raise BadRequestError(f"重排模型「{model.name}」未配置 API Key")

        base = resolve_rerank_openai_compat_base(model)
        url = f"{base.rstrip('/')}/reranks"
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
