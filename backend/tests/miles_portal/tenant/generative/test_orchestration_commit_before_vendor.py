"""生成编排：厂商 HTTP 前须 commit 释放 DB 连接。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor
from miles_core.tenant import TenantContext


class _TxnDb:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


def _image_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=uuid4(),
        name="生图",
        provider="qwen",
        model_name="wanx-v1",
        model_code="wanx-v1",
        vendor=ModelVendor.QWEN.value,
        model_type=ModelCapabilityType.IMAGE_GEN.value,
        extra={},
    )


def _video_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=uuid4(),
        name="生视频",
        provider="qwen",
        model_name="wan2.2-i2v-plus",
        model_code="wan2.2-i2v-plus",
        vendor=ModelVendor.QWEN.value,
        model_type=ModelCapabilityType.VIDEO_GEN.value,
        extra={},
    )


def _tts_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=uuid4(),
        name="TTS",
        provider="qwen",
        model_name="cosyvoice-v1",
        model_code="cosyvoice-v1",
        vendor=ModelVendor.QWEN.value,
        model_type=ModelCapabilityType.TTS.value,
        extra={},
    )


@pytest.mark.asyncio
async def test_generate_image_commits_before_vendor_http():
    db = _TxnDb()

    async def fake_vendor(*_a, **_k):
        db.events.append("vendor")
        return [b"\x89PNG\r\n"]

    with (
        patch(
            "miles_portal.tenant.generative.services.orchestration.assert_generative_quota",
            new_callable=AsyncMock,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.check_generative_prompt",
            new_callable=AsyncMock,
            side_effect=lambda _db, _ctx, p: p,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.generate_image_bytes",
            new_callable=AsyncMock,
            side_effect=fake_vendor,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.register_media_asset",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id=uuid4()),
        ),
    ):
        from miles_portal.tenant.generative.services.orchestration import generate_image_for_model

        await generate_image_for_model(db, _ctx(), _image_model(), prompt="一只猫")

    assert db.events == ["commit", "vendor"]


@pytest.mark.asyncio
async def test_generate_video_commits_before_vendor_http():
    db = _TxnDb()

    async def fake_vendor(*_a, **_k):
        db.events.append("vendor")
        return b"video-bytes"

    with (
        patch(
            "miles_portal.tenant.generative.services.orchestration.assert_generative_quota",
            new_callable=AsyncMock,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.check_generative_prompt",
            new_callable=AsyncMock,
            side_effect=lambda _db, _ctx, p: p,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.generate_video_bytes",
            new_callable=AsyncMock,
            side_effect=fake_vendor,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.register_media_asset",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id=uuid4()),
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.extract_video_cover_jpeg",
            return_value=None,
        ),
    ):
        from miles_portal.tenant.generative.services.orchestration import generate_video_for_model

        await generate_video_for_model(db, _ctx(), _video_model(), prompt="海浪")

    assert db.events == ["commit", "vendor"]


@pytest.mark.asyncio
async def test_generate_speech_commits_before_vendor_http():
    db = _TxnDb()

    async def fake_vendor(*_a, **_k):
        db.events.append("vendor")
        return b"audio-bytes"

    with (
        patch(
            "miles_portal.tenant.generative.services.orchestration.generate_tts_bytes",
            new_callable=AsyncMock,
            side_effect=fake_vendor,
        ),
        patch(
            "miles_portal.tenant.generative.services.orchestration.persist_generated_bytes",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ),
    ):
        from miles_portal.tenant.generative.services.orchestration import generate_speech_for_model

        await generate_speech_for_model(db, _ctx(), _tts_model(), text="你好")

    assert db.events == ["commit", "vendor"]
