"""Rerank provider 与 catalog 种子。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_ai.integrations.rerank.constants import INVOKE_MODE_DASHSCOPE, INVOKE_MODE_OPENAI_COMPATIBLE
from miles_ai.integrations.rerank.model_meta import (
    invoke_mode_from_model,
    resolve_rerank_openai_compat_url,
)
from miles_ai.integrations.rerank.providers.dashscope import DashScopeRerankProvider
from miles_ai.integrations.rerank.registry import known_invoke_modes, rerank_documents_for_model
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor


def _qwen_rerank_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": None,
        "name": "通义 qwen3-rerank",
        "provider": "qwen",
        "model_name": "qwen3-rerank",
        "model_type": ModelCapabilityType.RERANK.value,
        "vendor": ModelVendor.QWEN.value,
        "api_key_encrypted": "sk-test",
        "api_base": "https://dashscope.aliyuncs.com/compatible-api/v1",
        "extra": {"invoke_mode": INVOKE_MODE_OPENAI_COMPATIBLE},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_known_rerank_invoke_modes():
    modes = known_invoke_modes()
    assert "dashscope" in modes
    assert "openai_compatible" in modes


def test_qwen_rerank_defaults_to_openai_compatible():
    model = _qwen_rerank_model(extra={})
    assert invoke_mode_from_model(model) == "openai_compatible"


def test_dashscope_rerank_flat_payload():
    model = _qwen_rerank_model(
        extra={"invoke_mode": INVOKE_MODE_DASHSCOPE, "rerank_request_format": "flat"},
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "output": {
            "results": [
                {"index": 1, "relevance_score": 0.91},
                {"index": 0, "relevance_score": 0.42},
            ]
        }
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        hits = DashScopeRerankProvider().rerank(
            model,
            query="什么是重排模型？",
            documents=["文档A", "文档B"],
            top_n=2,
        )

    assert len(hits) == 2
    assert hits[0]["index"] == 1
    assert hits[0]["relevance_score"] == pytest.approx(0.91)
    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "qwen3-rerank"
    assert payload["query"] == "什么是重排模型？"
    assert payload["documents"] == ["文档A", "文档B"]
    assert payload["top_n"] == 2
    assert "instruct" in payload


def test_dashscope_rerank_nested_payload():
    model = _qwen_rerank_model(
        model_name="gte-rerank-v2",
        extra={"invoke_mode": INVOKE_MODE_DASHSCOPE, "rerank_request_format": "nested"},
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"output": {"results": [{"index": 0, "relevance_score": 0.8}]}}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        hits = DashScopeRerankProvider().rerank(
            model,
            query="query",
            documents=["doc"],
            top_n=1,
        )

    assert len(hits) == 1
    payload = mock_post.call_args.kwargs["json"]
    assert "input" in payload
    assert payload["input"]["query"] == "query"
    assert payload["parameters"]["top_n"] == 1


def test_openai_compat_ignores_native_rerank_api_base_override():
    model = _qwen_rerank_model(
        api_base="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    )
    assert resolve_rerank_openai_compat_url(model) == "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"


def test_registry_routes_qwen_rerank():
    model = _qwen_rerank_model()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"results": [{"index": 0, "relevance_score": 0.75}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        hits = rerank_documents_for_model(
            model,
            query="hello",
            documents=["world"],
            top_n=1,
        )

    assert hits[0]["relevance_score"] == pytest.approx(0.75)
    url = mock_post.call_args.args[0]
    assert url.endswith("/reranks")


def test_dashscope_rerank_missing_api_key():
    model = _qwen_rerank_model(api_key_encrypted=None)
    with pytest.raises(BadRequestError):
        DashScopeRerankProvider().rerank(
            model,
            query="q",
            documents=["d"],
        )
