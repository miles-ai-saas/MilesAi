"""豆包 / 火山方舟生图 Provider。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.integrations.generative.image.providers.volcengine_image import generate_volcengine_image
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor


def _doubao_image_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "SeedEdit",
        "provider": "doubao",
        "model_name": "doubao-seededit-3-0-i2i-250628",
        "model_code": "doubao-seededit-3-0-i2i-250628",
        "vendor": ModelVendor.DOUBAO.value,
        "model_type": ModelCapabilityType.IMAGE_GEN.value,
        "api_key_encrypted": "sk-test",
        "extra": {},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


@pytest.mark.asyncio
async def test_seededit_requires_reference_image():
    model = _doubao_image_model()
    with pytest.raises(BadRequestError, match="图生图"):
        await generate_volcengine_image(model, prompt="编辑", size="1024x1024", n=1)


@pytest.mark.asyncio
async def test_volcengine_image_passes_reference_in_body():
    model = _doubao_image_model(model_name="doubao-seedream-4-0-250828")
    ref = "data:image/png;base64,xx"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"b64_json": "aGk="}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.integrations.generative.image.providers.volcengine_image.httpx.AsyncClient",
        return_value=mock_client,
    ):
        blobs = await generate_volcengine_image(
            model,
            prompt="一只猫",
            size="1024x1024",
            n=1,
            reference_image_data_url=ref,
        )

    assert blobs == [b"hi"]
    body = mock_client.post.await_args.kwargs["json"]
    assert body["image"] == ref
