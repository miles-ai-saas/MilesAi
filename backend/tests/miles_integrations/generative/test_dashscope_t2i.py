"""万相（dashscope）生图 Provider。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor
from miles_integrations.generative.image.providers.dashscope_t2i import generate_dashscope_t2i


def _qwen_image_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "万相",
        "provider": "qwen",
        "model_name": "wanx-v1",
        "model_code": "wanx-v1",
        "vendor": ModelVendor.QWEN.value,
        "model_type": ModelCapabilityType.IMAGE_GEN.value,
        "api_key_encrypted": "sk-test",
        "extra": {},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def _mock_client(payload: dict):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    client.get = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_missing_api_key_is_rejected():
    model = _qwen_image_model(api_key_encrypted=None)
    with pytest.raises(BadRequestError, match="未配置 API Key"):
        await generate_dashscope_t2i(model, prompt="一只猫", size="1024x1024")


@pytest.mark.asyncio
async def test_inline_result_is_decoded():
    """同步返回（无 task_id）时直接取 output.results[].b64_image。"""
    client = _mock_client({"output": {"results": [{"b64_image": "aGk="}]}})
    model = _qwen_image_model()

    with patch(
        "miles_integrations.generative.image.providers.dashscope_t2i.httpx.AsyncClient",
        return_value=client,
    ):
        blobs = await generate_dashscope_t2i(model, prompt="一只猫", size="1024x1024")

    assert blobs == [b"hi"]


@pytest.mark.asyncio
async def test_request_log_must_not_leak_api_key_or_reference_image(caplog):
    """回归：请求日志曾把 ``Authorization: Bearer <key>`` 与整段 body（含 base64 垫图）打进 INFO。"""
    ref = "data:image/png;base64,REFERENCE_IMAGE_PAYLOAD"
    client = _mock_client({"output": {"results": [{"b64_image": "aGk="}]}})
    model = _qwen_image_model()

    with (
        caplog.at_level("INFO"),
        patch(
            "miles_integrations.generative.image.providers.dashscope_t2i.httpx.AsyncClient",
            return_value=client,
        ),
    ):
        await generate_dashscope_t2i(
            model,
            prompt="一只猫",
            size="1024x1024",
            reference_image_data_url=ref,
        )

    assert "sk-test" not in caplog.text
    assert "Authorization" not in caplog.text
    assert "REFERENCE_IMAGE_PAYLOAD" not in caplog.text
