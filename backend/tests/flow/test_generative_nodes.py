"""画布生图/生视频节点：同步分支的模型解析器来自 RunContext 注入（L1）。"""

import asyncio
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.flow_runtime.nodes import image_generate as image_node
from app.flow_runtime.nodes import video_generate as video_node
from app.flow_runtime.types import RunContext
from app.integrations.generative.types import ImageGenerateResult, VideoGenerateResult


def _run(coro):
    return asyncio.run(coro)


class _FakeSession:
    """替代 AsyncSessionLocal 的假会话（同步分支自开会话处使用）。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        pass


def test_image_generate_sync_without_resolver_raises():
    ctx = RunContext(tenant_id=str(uuid4()), generative_image_async=False, agent_config={})
    node = {"prompt": "画一只猫", "model_config_id": str(uuid4())}
    with pytest.raises(BadRequestError, match="未装配"):
        _run(image_node.image_generate(node, {}, ctx))


def test_video_generate_sync_without_resolver_raises():
    ctx = RunContext(tenant_id=str(uuid4()), generative_video_async=False)
    node = {"prompt": "一段小短片"}
    with pytest.raises(BadRequestError, match="未装配"):
        _run(video_node.video_generate(node, {}, ctx))


def test_image_generate_sync_with_injected_resolver(monkeypatch):
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _FakeSession)

    mid, att = uuid4(), uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_model=None, agent_config=None):
        assert model_config_id == mid
        return type("Model", (), {"id": mid})()

    async def fake_generate(db, ctx, model, **kwargs):
        return ImageGenerateResult(attachment_ids=[att], mime_type="image/png", media_asset_ids=[])

    monkeypatch.setattr(image_node, "generate_image_for_model", fake_generate)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),  # tenant_context_from_run 要求 user_id 非空
        generative_image_async=False,
        agent_config={},
        resolve_generative_image=fake_resolve,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    out = _run(image_node.image_generate(node, {}, ctx))
    assert out["kind"] == "image"
    assert str(out["attachment_id"]) == str(att)


def test_video_generate_sync_with_injected_resolver(monkeypatch):
    monkeypatch.setattr(video_node, "AsyncSessionLocal", _FakeSession)

    mid, att = uuid4(), uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_config=None):
        assert model_config_id == mid
        return type("Model", (), {"id": mid})()

    async def fake_generate(db, ctx, model, **kwargs):
        return VideoGenerateResult(attachment_id=att, mime_type="video/mp4", duration_sec=5, media_asset_id=None)

    monkeypatch.setattr(video_node, "generate_video_for_model", fake_generate)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),  # tenant_context_from_run 要求 user_id 非空
        generative_video_async=False,
        resolve_generative_video=fake_resolve,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}
    out = _run(video_node.video_generate(node, {}, ctx))
    assert out["kind"] == "video"
    assert str(out["attachment_id"]) == str(att)


def test_image_generate_async_submits_via_callback(monkeypatch):
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _FakeSession)

    mid, job = uuid4(), uuid4()

    async def fake_submit(db, tenant_ctx, *, prompt, size, n, image_attachment_id,
                          model_config_id, agent_id=None, agent_config=None):
        assert model_config_id == mid
        return job

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        agent_id=str(uuid4()),
        generative_image_async=True,
        agent_config={},
        submit_generative_image=fake_submit,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    out = _run(image_node.image_generate(node, {}, ctx))
    assert out == {
        "kind": "image",
        "status": "pending",
        "generative_job_id": str(job),
        "message": "生图任务已提交，请通过 generative_job_id 查询进度",
    }


def test_video_generate_async_submits_via_callback(monkeypatch):
    monkeypatch.setattr(video_node, "AsyncSessionLocal", _FakeSession)

    mid, job = uuid4(), uuid4()

    async def fake_submit(db, tenant_ctx, *, prompt, duration, resolution,
                          image_attachment_id, last_frame_attachment_id,
                          model_config_id, agent_id=None, agent_config=None):
        assert duration == 5
        assert model_config_id == mid
        return job

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        agent_id=str(uuid4()),
        generative_video_async=True,
        submit_generative_video=fake_submit,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}
    out = _run(video_node.video_generate(node, {}, ctx))
    assert out == {
        "kind": "video",
        "status": "pending",
        "generative_job_id": str(job),
        "message": "生视频任务已提交，请通过 generative_job_id 查询进度",
    }


def test_image_generate_async_without_submitter_falls_back_to_sync():
    """async 打开但未注入 submit（Celery 未启用）→ 落同步分支；无 resolver 时报未装配。"""
    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_image_async=True,
        agent_config={},
    )
    node = {"prompt": "画一只猫", "model_config_id": str(uuid4())}
    with pytest.raises(BadRequestError, match="未装配"):
        _run(image_node.image_generate(node, {}, ctx))
