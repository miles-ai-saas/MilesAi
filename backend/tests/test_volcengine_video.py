"""豆包 / 火山方舟生视频 Provider。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.types import VideoGenerateResult
from app.integrations.generative.video.providers.volcengine_video import (
    _build_request_body,
    generate_volcengine_video,
)
from app.integrations.generative.volcengine_client import (
    normalize_volcengine_resolution,
    volcengine_poll_url,
    volcengine_submit_url,
)
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor


def _doubao_video_model(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "Seedance",
        "provider": "doubao",
        "model_name": "doubao-seedance-1-5-pro-251215",
        "model_code": "doubao-seedance-1-5-pro",
        "vendor": ModelVendor.DOUBAO.value,
        "model_type": ModelCapabilityType.VIDEO_GEN.value,
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_encrypted": "sk-test",
        "extra": {},
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_normalize_resolution():
    assert normalize_volcengine_resolution("720P") == "720p"
    assert normalize_volcengine_resolution("1080p") == "1080p"


def test_volcengine_urls_from_model():
    m = _doubao_video_model()
    assert volcengine_submit_url(m).endswith("/contents/generations/tasks")
    assert "cgt-abc" in volcengine_poll_url(m, "cgt-abc")


def test_build_request_body_text_to_video():
    m = _doubao_video_model(extra={"video_ratio": "9:16", "video_duration": 8})
    body = _build_request_body(
        m,
        prompt="海边日落",
        duration=5,
        resolution="720P",
        ratio="16:9",
        first_frame_data_url=None,
    )
    assert body["model"] == "doubao-seedance-1-5-pro-251215"
    assert body["content"] == [{"type": "text", "text": "海边日落"}]
    assert body["duration"] == 8
    assert body["resolution"] == "720p"
    assert body["ratio"] == "16:9"


def test_build_request_body_i2v():
    m = _doubao_video_model()
    body = _build_request_body(
        m,
        prompt="动起来",
        duration=5,
        resolution="720p",
        ratio="adaptive",
        first_frame_data_url="data:image/png;base64,abc",
    )
    assert len(body["content"]) == 2
    assert body["content"][1]["type"] == "image_url"


def test_build_request_body_first_last_frame():
    m = _doubao_video_model()
    body = _build_request_body(
        m,
        prompt="从 A 过渡到 B",
        duration=5,
        resolution="720p",
        ratio="adaptive",
        first_frame_data_url="data:image/png;base64,first",
        last_frame_data_url="data:image/png;base64,last",
    )
    assert len(body["content"]) == 3
    assert body["content"][1]["role"] == "first_frame"
    assert body["content"][2]["role"] == "last_frame"


def test_build_content_last_without_first_raises():
    with pytest.raises(BadRequestError, match="首尾帧"):
        from app.integrations.generative.video.providers.volcengine_video import _build_content

        _build_content("x", None, "data:image/png;base64,last")


def test_build_request_body_missing_model_name():
    m = _doubao_video_model(model_name="")
    with pytest.raises(BadRequestError, match="model_name"):
        _build_request_body(
            m,
            prompt="x",
            duration=5,
            resolution="720p",
            ratio="16:9",
            first_frame_data_url=None,
        )


@pytest.mark.asyncio
async def test_generate_volcengine_video_happy_path():
    m = _doubao_video_model()
    mp4 = b"\x00\x00\x00\x18ftypmp42"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "cgt-test-1"}

    with (
        patch("httpx.AsyncClient") as client_cls,
        patch(
            "app.integrations.generative.video.providers.volcengine_video.poll_volcengine_video_task",
            new_callable=AsyncMock,
            return_value={"status": "succeeded", "content": {"video_url": "https://example.com/v.mp4"}},
        ),
        patch(
            "app.integrations.generative.video.providers.volcengine_video.download_remote_bytes",
            new_callable=AsyncMock,
            return_value=mp4,
        ),
    ):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = AsyncMock(return_value=mock_resp)
        client_cls.return_value = client

        out = await generate_volcengine_video(m, prompt="测试视频", duration=5)

    assert out == mp4
    call_json = client.post.call_args.kwargs["json"]
    assert call_json["model"] == m.model_name


@pytest.mark.asyncio
async def test_generate_video_for_model_doubao_route():
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )
    model = _doubao_video_model()
    att_id = uuid4()

    with (
        patch(
            "app.integrations.generative.quota.assert_generative_quota",
            new_callable=AsyncMock,
        ),
        patch(
            "app.integrations.generative.video.service.generate_volcengine_video",
            new_callable=AsyncMock,
            return_value=b"\x00\x00\x00\x18ftypmp42",
        ),
        patch(
            "app.integrations.generative.video.service.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=att_id,
        ),
        patch(
            "app.tenant.media_assets.services.media_asset.register_media_asset",
            new_callable=AsyncMock,
        ),
    ):
        from app.integrations.generative.video.service import generate_video_for_model

        result = await generate_video_for_model(
            AsyncMock(),
            ctx,
            model,
            prompt="海浪",
        )

    assert isinstance(result, VideoGenerateResult)
    assert result.attachment_id == att_id
