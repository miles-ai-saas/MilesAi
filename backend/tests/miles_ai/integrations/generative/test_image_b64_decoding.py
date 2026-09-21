"""生图 Provider 对脏 base64 响应的容错。

三个 Provider 的 ``b64_json`` / ``b64_image`` 都来自外部响应，可能被截断或夹带非
base64 字符。此前直接把 ``binascii.Error`` 冒到任务层，报错只有一行
"Invalid base64-encoded string"，看不出是哪家返回的脏数据。
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.integrations.generative.image.providers._decoding import decode_b64_image
from miles_ai.integrations.generative.image.providers.dashscope_t2i import generate_dashscope_t2i
from miles_ai.integrations.generative.image.providers.openai_images import generate_openai_images
from miles_ai.integrations.generative.image.providers.volcengine_image import generate_volcengine_image
from miles_common.exceptions import AppError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor

_GARBAGE = "!!!not-base64!!!"


# --- 共享解码助手 ----------------------------------------------------------- #


def test_decodes_valid_base64():
    assert decode_b64_image("aGk=") == b"hi"


@pytest.mark.parametrize("bad", [_GARBAGE, "aGk", "中文"])
def test_dirty_base64_returns_none_instead_of_raising(bad):
    """非法字符、长度不合法、非 ASCII 一律返回 None（并记 warning）。

    空串不在此列：它会解码成 ``b""``，而三个调用点都会先用 ``if b64:`` 过滤掉空值。
    """
    assert decode_b64_image(bad) is None


# --- 三个 Provider 的端到端容错 ---------------------------------------------- #


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


def _model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "生图模型",
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


@pytest.mark.asyncio
async def test_dashscope_all_dirty_reports_readable_error():
    client = _mock_client({"output": {"results": [{"b64_image": _GARBAGE}]}})
    with patch(
        "miles_ai.integrations.generative.image.providers.dashscope_t2i.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(AppError, match="无图片数据"):
            await generate_dashscope_t2i(_model(), prompt="猫", size="1024x1024")


@pytest.mark.asyncio
async def test_dashscope_one_dirty_one_valid_keeps_the_valid_one():
    client = _mock_client({"output": {"results": [{"b64_image": _GARBAGE}, {"b64_image": "aGk="}]}})
    with patch(
        "miles_ai.integrations.generative.image.providers.dashscope_t2i.httpx.AsyncClient",
        return_value=client,
    ):
        blobs = await generate_dashscope_t2i(_model(), prompt="猫", size="1024x1024")

    assert blobs == [b"hi"]


@pytest.mark.asyncio
async def test_volcengine_all_dirty_reports_readable_error():
    client = _mock_client({"data": [{"b64_json": _GARBAGE}]})
    model = _model(model_name="doubao-seedream-4-0-250828", vendor=ModelVendor.DOUBAO.value)
    with patch(
        "miles_ai.integrations.generative.image.providers.volcengine_image.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(AppError, match="未返回可用图片数据"):
            await generate_volcengine_image(model, prompt="猫", size="1024x1024")


@pytest.mark.asyncio
async def test_openai_images_all_dirty_reports_readable_error():
    client = _mock_client({"data": [{"b64_json": _GARBAGE}]})
    with patch(
        "miles_ai.integrations.generative.image.providers.openai_images.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(AppError, match="未返回可用图片数据"):
            await generate_openai_images(_model(provider="openai", vendor=ModelVendor.OPENAI.value), prompt="猫", size="1024x1024")
