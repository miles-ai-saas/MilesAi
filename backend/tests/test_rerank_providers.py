"""Rerank provider 与 catalog 种子。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.integrations.rerank.constants import INVOKE_MODE_DASHSCOPE
from app.integrations.rerank.model_meta import invoke_mode_from_model
from app.integrations.rerank.providers.dashscope import DashScopeRerankProvider
from app.integrations.rerank.registry import known_invoke_modes, rerank_documents_for_model
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor


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
        "api_base": (
            "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        ),
        "extra": {"invoke_mode": INVOKE_MODE_DASHSCOPE, "rerank_request_format": "flat"},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_catalog_contains_rerank_models():
    from pathlib import Path

    catalog_src = Path(__file__).resolve().parents[1] / "scripts" / "seed" / "model_catalog.py"
    text = catalog_src.read_text(encoding="utf-8")
    assert '"model_code": "qwen3-rerank"' in text
    assert '"model_code": "gte-rerank-v2"' in text


def test_known_rerank_invoke_modes():
    modes = known_invoke_modes()
    assert "dashscope" in modes
    assert "openai_compatible" in modes


def test_qwen_rerank_defaults_to_dashscope():
    model = _qwen_rerank_model(extra={})
    assert invoke_mode_from_model(model) == INVOKE_MODE_DASHSCOPE


def test_dashscope_rerank_flat_payload():
    model = _qwen_rerank_model()
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
    mock_response.json.return_value = {
        "output": {"results": [{"index": 0, "relevance_score": 0.8}]}
    }

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


def test_registry_routes_qwen_rerank():
    model = _qwen_rerank_model()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "output": {"results": [{"index": 0, "relevance_score": 0.75}]}
    }

    with patch("httpx.post", return_value=mock_response):
        hits = rerank_documents_for_model(
            model,
            query="hello",
            documents=["world"],
            top_n=1,
        )

    assert hits[0]["relevance_score"] == pytest.approx(0.75)


def test_dashscope_rerank_missing_api_key():
    model = _qwen_rerank_model(api_key_encrypted=None)
    with pytest.raises(BadRequestError):
        DashScopeRerankProvider().rerank(
            model,
            query="q",
            documents=["d"],
        )
