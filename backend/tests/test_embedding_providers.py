"""Embedding provider 注册表与 OpenAI 兼容向量化。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.integrations.embeddings.constants import (
    EXTRA_EMBEDDING_DIMENSION,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from app.integrations.embeddings.model_meta import (
    embedding_batch_size_from_model,
    invoke_mode_from_model,
)
from app.integrations.embeddings.providers.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
)
from app.integrations.embeddings.registry import embed_texts_for_model, known_invoke_modes
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor


def _qwen_embedding_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": None,
        "name": "通义 text-embedding-v4",
        "provider": "qwen",
        "model_name": "text-embedding-v4",
        "model_type": ModelCapabilityType.EMBEDDING.value,
        "vendor": ModelVendor.QWEN.value,
        "api_key_encrypted": "sk-test",
        "extra": {EXTRA_EMBEDDING_DIMENSION: 1024},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_known_invoke_modes():
    modes = known_invoke_modes()
    assert "local" in modes
    assert "openai_compatible" in modes
    assert "litellm" in modes


def test_qwen_defaults_to_openai_compatible():
    model = _qwen_embedding_model()
    assert invoke_mode_from_model(model) == INVOKE_MODE_OPENAI_COMPATIBLE


def test_qwen_embedding_batch_size_capped_at_10():
    model = _qwen_embedding_model(extra={EXTRA_EMBEDDING_DIMENSION: 1024, "embedding_batch_size": 25})
    assert embedding_batch_size_from_model(model) == 10


def test_openai_compatible_embed_texts():
    model = _qwen_embedding_model(
        extra={
            EXTRA_EMBEDDING_DIMENSION: 1024,
            "invoke_mode": INVOKE_MODE_OPENAI_COMPATIBLE,
        }
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.3, 0.4]},
        ]
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        vectors = OpenAICompatibleEmbeddingProvider().embed_texts(model, ["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    url = mock_post.call_args.args[0]
    assert call_kwargs["json"]["model"] == "text-embedding-v4"
    assert call_kwargs["json"]["encoding_format"] == "float"
    assert call_kwargs["json"]["dimensions"] == 1024
    assert "dashscope.aliyuncs.com" in url


def test_registry_routes_qwen_via_openai_compatible():
    model = _qwen_embedding_model()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "data": [{"index": 0, "embedding": [0.5] * 1024}]
    }

    with patch("httpx.post", return_value=mock_response):
        vectors = embed_texts_for_model(model, ["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 1024


def test_openai_compatible_missing_api_key():
    model = _qwen_embedding_model(api_key_encrypted=None)
    with pytest.raises(BadRequestError):
        OpenAICompatibleEmbeddingProvider().embed_texts(model, ["x"])


def test_openai_compatible_batches_over_10_texts():
    model = _qwen_embedding_model()
    texts = [f"t{i}" for i in range(12)]

    def _fake_response(batch_len: int):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [{"index": i, "embedding": [0.1]} for i in range(batch_len)]
        }
        return mock_response

    with patch("httpx.post", side_effect=lambda *a, **k: _fake_response(len(k["json"]["input"]))) as mock_post:
        vectors = OpenAICompatibleEmbeddingProvider().embed_texts(model, texts)

    assert len(vectors) == 12
    assert mock_post.call_count == 2
    assert len(mock_post.call_args_list[0].kwargs["json"]["input"]) == 10
    assert len(mock_post.call_args_list[1].kwargs["json"]["input"]) == 2
