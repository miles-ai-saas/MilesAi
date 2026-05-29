"""生图集成与工具。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.tenant import TenantContext
from app.integrations.generative.registry import resolve_invoke_mode
from app.integrations.generative.types import ImageGenerateResult
from app.integrations.langchain.tool_agent import _artifacts_from_tool_output
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor
from app.integrations.generative.constants import (
    INVOKE_DASHSCOPE_T2I,
    INVOKE_OPENAI_IMAGES,
    INVOKE_VOLCENGINE_IMAGE,
)


def _image_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "生图",
        "provider": "qwen",
        "model_name": "wanx-v1",
        "model_code": "wanx-v1",
        "vendor": ModelVendor.QWEN.value,
        "model_type": ModelCapabilityType.IMAGE_GEN.value,
        "extra": {},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_resolve_invoke_mode_qwen():
    m = _image_model()
    assert resolve_invoke_mode(m, capability=ModelCapabilityType.IMAGE_GEN.value) == INVOKE_DASHSCOPE_T2I


def test_resolve_invoke_mode_doubao():
    m = _image_model(vendor=ModelVendor.DOUBAO.value, model_name="doubao-seededit-3-0-i2i-250628")
    assert resolve_invoke_mode(m, capability=ModelCapabilityType.IMAGE_GEN.value) == INVOKE_VOLCENGINE_IMAGE


def test_resolve_invoke_mode_explicit():
    m = _image_model(extra={"invoke_mode": INVOKE_OPENAI_IMAGES})
    assert resolve_invoke_mode(m, capability=ModelCapabilityType.IMAGE_GEN.value) == INVOKE_OPENAI_IMAGES


def test_artifacts_from_tool_output():
    aid = uuid4()
    arts = _artifacts_from_tool_output(
        {
            "kind": "image",
            "attachment_id": str(aid),
            "mime_type": "image/png",
            "message": "ok",
        }
    )
    assert len(arts) == 1
    assert arts[0].attachment_id == aid


@pytest.mark.asyncio
async def test_generate_image_for_model_with_reference():
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )
    model = _image_model(vendor=ModelVendor.DOUBAO.value)
    ref_id = uuid4()
    att_id = uuid4()

    with (
        patch(
            "app.integrations.generative.quota.assert_generative_quota",
            new_callable=AsyncMock,
        ),
        patch(
            "app.integrations.generative.image.service.reference_image_data_url",
            new_callable=AsyncMock,
            return_value="data:image/png;base64,abc",
        ),
        patch(
            "app.integrations.generative.image.service._generate_bytes",
            new_callable=AsyncMock,
            return_value=[b"\x89PNG\r\n"],
        ) as gen,
        patch(
            "app.integrations.generative.image.service.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=att_id,
        ),
        patch(
            "app.tenant.media_assets.services.media_asset.register_media_asset",
            new_callable=AsyncMock,
        ),
        patch(
            "app.integrations.generative.compliance.check_generative_prompt",
            new_callable=AsyncMock,
            side_effect=lambda _db, _ctx, p: p,
        ),
    ):
        from app.integrations.generative.image.service import generate_image_for_model

        await generate_image_for_model(
            AsyncMock(),
            ctx,
            model,
            prompt="改成油画风格",
            reference_attachment_id=ref_id,
        )
        gen.assert_awaited_once()
        assert gen.await_args.kwargs["reference_image_data_url"] == "data:image/png;base64,abc"


@pytest.mark.asyncio
async def test_generate_image_for_model_persists():
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )
    model = _image_model()
    att_id = uuid4()

    with (
        patch(
            "app.integrations.generative.quota.assert_generative_quota",
            new_callable=AsyncMock,
        ),
        patch(
            "app.integrations.generative.image.service._generate_bytes",
            new_callable=AsyncMock,
            return_value=[b"\x89PNG\r\n"],
        ),
        patch(
            "app.integrations.generative.image.service.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=att_id,
        ),
        patch(
            "app.tenant.media_assets.services.media_asset.register_media_asset",
            new_callable=AsyncMock,
        ),
        patch(
            "app.integrations.generative.compliance.check_generative_prompt",
            new_callable=AsyncMock,
            side_effect=lambda _db, _ctx, p: p,
        ),
    ):
        from app.integrations.generative.image.service import generate_image_for_model

        result = await generate_image_for_model(
            AsyncMock(),
            ctx,
            model,
            prompt="一只猫",
        )

    assert isinstance(result, ImageGenerateResult)
    assert result.attachment_ids == [att_id]
