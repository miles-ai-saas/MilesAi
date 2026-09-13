"""生视频集成（万相 / 豆包 HTTP）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from miles_ai.integrations.generative.constants import INVOKE_DASHSCOPE_T2V, INVOKE_VOLCENGINE_VIDEO
from miles_ai.integrations.generative.registry import resolve_invoke_mode
from miles_ai.integrations.generative.types import VideoGenerateResult
from miles_ai.integrations.langchain.tool_agent import artifacts_from_tool_output
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor
from miles_core.tenant import TenantContext


def _video_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "万相生视频",
        "provider": "qwen",
        "model_name": "wan2.2-i2v-plus",
        "model_code": "wan2.2-i2v-plus",
        "vendor": ModelVendor.QWEN.value,
        "model_type": ModelCapabilityType.VIDEO_GEN.value,
        "extra": {},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_resolve_video_invoke_mode_qwen():
    m = _video_model()
    assert resolve_invoke_mode(m, capability=ModelCapabilityType.VIDEO_GEN.value) == INVOKE_DASHSCOPE_T2V


def test_resolve_video_invoke_mode_doubao():
    m = _video_model(vendor=ModelVendor.DOUBAO.value, provider="doubao")
    assert resolve_invoke_mode(m, capability=ModelCapabilityType.VIDEO_GEN.value) == INVOKE_VOLCENGINE_VIDEO


def test_artifacts_from_video_tool_output():
    aid = uuid4()
    arts = artifacts_from_tool_output(
        {
            "kind": "video",
            "attachment_id": str(aid),
            "mime_type": "video/mp4",
            "message": "视频已生成",
        }
    )
    assert len(arts) == 1
    assert arts[0].kind == "video"
    assert arts[0].attachment_id == aid


@pytest.mark.asyncio
async def test_generate_video_for_model_persists():
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )
    model = _video_model()
    att_id = uuid4()

    with (
        patch(
            "miles_portal.tenant.generative.services.orchestration.assert_generative_quota",
            new_callable=AsyncMock,
        ),
        patch(
            "miles_ai.integrations.generative.video.service.generate_dashscope_video",
            new_callable=AsyncMock,
            return_value=b"\x00\x00\x00\x18ftypmp42",
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=att_id,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.register_media_asset",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id=uuid4()),
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.check_generative_prompt",
            new_callable=AsyncMock,
            side_effect=lambda _db, _ctx, p: p,
        ),
    ):
        from miles_portal.tenant.generative.services.orchestration import generate_video_for_model

        result = await generate_video_for_model(
            AsyncMock(),
            ctx,
            model,
            prompt="海浪拍岸",
            duration=5,
        )

    assert isinstance(result, VideoGenerateResult)
    assert result.attachment_id == att_id
    assert result.mime_type == "video/mp4"
