"""生视频集成（万相 / 豆包 HTTP）。"""

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor
from miles_core.tenant import TenantContext
from miles_integrations.generative.constants import INVOKE_DASHSCOPE_T2V, INVOKE_VOLCENGINE_VIDEO
from miles_integrations.generative.registry import resolve_invoke_mode
from miles_integrations.generative.types import VideoGenerateResult
from miles_integrations.langchain.tool_agent import artifacts_from_tool_output


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
            "miles_integrations.generative.video.service.generate_dashscope_video",
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


@contextlib.contextmanager
def _video_pipeline(*, persist_returns=None, cover=b"cover-bytes"):
    persist = AsyncMock(side_effect=list(persist_returns)) if persist_returns is not None else AsyncMock(return_value=uuid4())
    register = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "miles_portal.tenant.generative.services.orchestration.assert_generative_quota",
                new_callable=AsyncMock,
            )
        )
        stack.enter_context(
            patch(
                "miles_portal.tenant.generative.services.orchestration.check_generative_prompt",
                new_callable=AsyncMock,
                side_effect=lambda _db, _ctx, p: p,
            )
        )
        stack.enter_context(
            patch(
                "miles_portal.tenant.generative.services.orchestration.generate_video_bytes",
                new_callable=AsyncMock,
                return_value=b"video-bytes",
            )
        )
        stack.enter_context(
            patch(
                "miles_portal.tenant.generative.services.orchestration.persist_generated_bytes",
                persist,
            )
        )
        stack.enter_context(
            patch(
                "miles_portal.tenant.generative.services.orchestration.register_media_asset",
                register,
            )
        )
        stack.enter_context(
            patch(
                "miles_portal.tenant.generative.services.orchestration.extract_video_cover_jpeg",
                return_value=cover,
            )
        )
        yield persist, register


def _video_ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


@pytest.mark.asyncio
async def test_video_cover_persisted_with_same_provenance_as_video():
    """封面与视频本体必须携带同一 purpose/resource_type/resource_id。

    二者来源标识若漂移，媒体资产归属会分裂（同一任务的产物挂到不同资源下）。
    """
    ctx = _video_ctx()
    agent_id = uuid4()
    video_att, cover_att = uuid4(), uuid4()
    with _video_pipeline(persist_returns=[video_att, cover_att]) as (persist, register):
        from miles_portal.tenant.generative.services.orchestration import generate_video_for_model

        result = await generate_video_for_model(
            AsyncMock(),
            ctx,
            _video_model(),
            prompt="海浪",
            purpose="flow_generated",
            agent_id=agent_id,
        )

    assert persist.await_count == 2
    video_call, cover_call = persist.await_args_list
    assert video_call.kwargs["data"] == b"video-bytes"
    assert video_call.kwargs["filename"] == "generated.mp4"
    assert video_call.kwargs["mime_type"] == "video/mp4"

    assert cover_call.kwargs["data"] == b"cover-bytes"
    assert cover_call.kwargs["filename"] == "generated-cover.jpg"
    assert cover_call.kwargs["mime_type"] == "image/jpeg"

    for key in ("purpose", "resource_type", "resource_id"):
        assert video_call.kwargs[key] == cover_call.kwargs[key], f"{key} 在封面与本体之间漂移"
    assert video_call.kwargs["purpose"] == "flow_generated"
    assert video_call.kwargs["resource_type"] == "agent"
    assert video_call.kwargs["resource_id"] == agent_id

    assert result.attachment_id == video_att
    assert register.await_args.kwargs["cover_attachment_id"] == cover_att


@pytest.mark.asyncio
async def test_video_cover_skipped_when_extraction_fails():
    ctx = _video_ctx()
    with _video_pipeline(cover=None) as (persist, register):
        from miles_portal.tenant.generative.services.orchestration import generate_video_for_model

        await generate_video_for_model(AsyncMock(), ctx, _video_model(), prompt="海浪")

    assert persist.await_count == 1
    assert register.await_args.kwargs["cover_attachment_id"] is None


@pytest.mark.asyncio
async def test_video_provenance_is_anonymous_without_agent():
    """无 agent_id 时 resource_type/resource_id 均为 None（两处调用一致）。"""
    ctx = _video_ctx()
    with _video_pipeline(persist_returns=[uuid4(), uuid4()]) as (persist, _register):
        from miles_portal.tenant.generative.services.orchestration import generate_video_for_model

        await generate_video_for_model(AsyncMock(), ctx, _video_model(), prompt="海浪")

    assert persist.await_count == 2
    for call in persist.await_args_list:
        assert call.kwargs["resource_type"] is None
        assert call.kwargs["resource_id"] is None
