"""LiteLLM 适配层单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai_stack.litellm.adapter import (
    litellm_chat_completion,
    resolve_litellm_model,
)
from app.common.exceptions import AppError, BadRequestError
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor


def _model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": None,
        "name": "测试模型",
        "provider": "deepseek",
        "model_name": "deepseek-v4-flash",
        "model_code": "deepseek-v4-flash",
        "vendor": ModelVendor.DEEPSEEK.value,
        "model_type": ModelCapabilityType.LLM.value,
        "api_base": "https://api.deepseek.com/v1",
        "api_key_encrypted": "sk-test",
        "extra": {},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_resolve_litellm_model_by_vendor():
    m = _model()
    assert resolve_litellm_model(m) == "deepseek/deepseek-v4-flash"


def test_resolve_litellm_model_explicit_extra():
    m = _model(extra={"litellm_model": "dashscope/qwen3.5-plus"})
    assert resolve_litellm_model(m) == "dashscope/qwen3.5-plus"


def test_resolve_litellm_model_passthrough_slash():
    m = _model(model_name="volcengine/ep-123", vendor=ModelVendor.DOUBAO.value, provider="doubao")
    assert resolve_litellm_model(m) == "volcengine/ep-123"


def test_resolve_litellm_model_doubao_volcengine():
    m = _model(
        model_name="doubao-seed-1-6-251015",
        vendor=ModelVendor.DOUBAO.value,
        provider="doubao",
    )
    assert resolve_litellm_model(m) == "volcengine/doubao-seed-1-6-251015"


def test_resolve_litellm_model_qwen_dashscope():
    m = _model(
        model_name="qwen3.5-plus",
        vendor=ModelVendor.QWEN.value,
        provider="qwen",
    )
    assert resolve_litellm_model(m) == "dashscope/qwen3.5-plus"


@pytest.mark.asyncio
async def test_litellm_chat_rejects_non_chat_type():
    m = _model(model_type=ModelCapabilityType.IMAGE_GEN.value)
    with pytest.raises(BadRequestError, match="仅支持对话类"):
        await litellm_chat_completion(m, [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_litellm_chat_success():
    m = _model()
    mock_choice = MagicMock()
    mock_choice.message.content = "hello"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_acompletion:
        out = await litellm_chat_completion(
            m, [{"role": "user", "content": "hi"}], temperature=0.5, max_tokens=100
        )

    assert out == "hello"
    mock_acompletion.assert_awaited_once()
    call_kwargs = mock_acompletion.await_args.kwargs
    assert call_kwargs["model"] == "deepseek/deepseek-v4-flash"
    assert call_kwargs["api_key"] == "sk-test"
    assert call_kwargs["api_base"] == "https://api.deepseek.com/v1"
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["max_tokens"] == 100


@pytest.mark.asyncio
async def test_litellm_chat_maps_litellm_error():
    m = _model()
    with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        with pytest.raises(AppError, match="模型调用失败"):
            await litellm_chat_completion(m, [{"role": "user", "content": "hi"}])


def test_litellm_embed_texts_success():
    from app.ai_stack.litellm.adapter import litellm_embed_texts

    item = MagicMock()
    item.embedding = [0.1, 0.2]
    mock_response = MagicMock()
    mock_response.data = [item, item]

    with patch("litellm.embedding", return_value=mock_response) as mock_emb:
        out = litellm_embed_texts(
            ["a", "b"],
            model="dashscope/text-embedding-v3",
            api_key="sk-x",
        )

    assert len(out) == 2
    assert out[0] == [0.1, 0.2]
    mock_emb.assert_called_once()
    assert mock_emb.call_args.kwargs["model"] == "dashscope/text-embedding-v3"
    assert mock_emb.call_args.kwargs["input"] == ["a", "b"]


def test_get_embeddings_uses_litellm_backend(monkeypatch):
    from app.ai_stack.langchain import embeddings as emb_mod
    from app.core.config import Settings

    emb_mod.get_embeddings.cache_clear()
    emb_mod._sentence_transformer.cache_clear()

    settings = Settings(
        embedding_backend="litellm",
        embedding_litellm_model="dashscope/text-embedding-v3",
        embedding_litellm_api_key="sk-test",
    )
    monkeypatch.setattr(emb_mod, "get_settings", lambda: settings)

    inst = emb_mod.get_embeddings()
    assert inst.__class__.__name__ == "LiteLLMEmbeddings"

    with patch(
        "app.ai_stack.litellm.adapter.litellm_embed_texts",
        return_value=[[1.0, 2.0]],
    ):
        assert emb_mod.embed_query("hello") == [1.0, 2.0]

    emb_mod.get_embeddings.cache_clear()
