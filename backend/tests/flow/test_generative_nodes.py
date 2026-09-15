"""画布生图/生视频节点：同步分支的模型解析器来自 RunContext 注入（L1）。"""

import asyncio
from uuid import uuid4

import pytest

from miles_ai.flow_runtime.nodes import image_generate as image_node
from miles_ai.flow_runtime.nodes import video_generate as video_node
from miles_ai.flow_runtime.types import RunContext
from miles_ai.integrations.generative.constants import PURPOSE_FLOW_GENERATED
from miles_ai.integrations.generative.types import ImageGenerateResult, VideoGenerateResult
from miles_common.exceptions import BadRequestError


def _run(coro):
    return asyncio.run(coro)


class _FakeSession:
    """替代 short_db_session 的假会话（同步分支自开会话处使用）。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        pass


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


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
    monkeypatch.setattr(image_node, "short_db_session", _FakeSession)

    mid, att = uuid4(), uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_model=None, agent_config=None):
        assert model_config_id == mid
        return type("Model", (), {"id": mid})()

    async def fake_generate(db, ctx, model, **kwargs):
        return ImageGenerateResult(attachment_ids=[att], mime_type="image/png", media_asset_ids=[])

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),  # tenant_context_from_run 要求 user_id 非空
        generative_image_async=False,
        agent_config={},
        resolve_generative_image=fake_resolve,
        generate_image_sync=fake_generate,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    out = _run(image_node.image_generate(node, {}, ctx))
    assert out["kind"] == "image"
    assert str(out["attachment_id"]) == str(att)


def test_image_generate_sync_without_orchestrator_raises(monkeypatch):
    """resolver 已装配但未注入 generate_image_sync ⇒ 报未装配。"""
    monkeypatch.setattr(image_node, "short_db_session", _FakeSession)
    mid = uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_model=None, agent_config=None):
        return type("Model", (), {"id": mid})()

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_image_async=False,
        agent_config={},
        resolve_generative_image=fake_resolve,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    with pytest.raises(BadRequestError, match="编排未装配"):
        _run(image_node.image_generate(node, {}, ctx))


def test_video_generate_sync_with_injected_resolver(monkeypatch):
    monkeypatch.setattr(video_node, "short_db_session", _FakeSession)

    mid, att = uuid4(), uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_config=None):
        assert model_config_id == mid
        return type("Model", (), {"id": mid})()

    async def fake_generate(db, ctx, model, **kwargs):
        return VideoGenerateResult(attachment_id=att, mime_type="video/mp4", duration_sec=5, media_asset_id=None)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),  # tenant_context_from_run 要求 user_id 非空
        generative_video_async=False,
        resolve_generative_video=fake_resolve,
        generate_video_sync=fake_generate,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}
    out = _run(video_node.video_generate(node, {}, ctx))
    assert out["kind"] == "video"
    assert str(out["attachment_id"]) == str(att)


def test_video_generate_sync_without_orchestrator_raises(monkeypatch):
    monkeypatch.setattr(video_node, "short_db_session", _FakeSession)
    mid = uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_config=None):
        return type("Model", (), {"id": mid})()

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_video_async=False,
        resolve_generative_video=fake_resolve,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}
    with pytest.raises(BadRequestError, match="编排未装配"):
        _run(video_node.video_generate(node, {}, ctx))


def test_image_generate_async_submits_via_callback(monkeypatch):
    monkeypatch.setattr(image_node, "short_db_session", _FakeSession)
    # 异步提交分支同样钉住回退：全局会话被调用即炸（raising=False 见 _Boom 说明）
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _Boom(), raising=False)

    mid, job = uuid4(), uuid4()
    seen_dbs = []

    async def fake_submit(db, tenant_ctx, *, prompt, size, n, image_attachment_id, model_config_id, agent_id=None, agent_config=None):
        assert model_config_id == mid
        seen_dbs.append(db)
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
    assert len(seen_dbs) == 1
    assert isinstance(seen_dbs[0], _FakeSession)


def test_video_generate_async_submits_via_callback(monkeypatch):
    monkeypatch.setattr(video_node, "short_db_session", _FakeSession)
    # 异步提交分支同样钉住回退：全局会话被调用即炸（raising=False 见 _Boom 说明）
    monkeypatch.setattr(video_node, "AsyncSessionLocal", _Boom(), raising=False)

    mid, job = uuid4(), uuid4()
    seen_dbs = []

    async def fake_submit(
        db, tenant_ctx, *, prompt, duration, resolution, image_attachment_id, last_frame_attachment_id, model_config_id, agent_id=None, agent_config=None
    ):
        assert duration == 5
        assert model_config_id == mid
        seen_dbs.append(db)
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
    assert len(seen_dbs) == 1
    assert isinstance(seen_dbs[0], _FakeSession)


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


def test_image_generate_sync_never_falls_back_to_global_session(monkeypatch):
    """同步生图站点：全局会话换成调用即炸替身，解析与编排仍必须走短会话。

    ``raising=False`` 是有意的：Task 1 之后本模块不再 import ``AsyncSessionLocal``，
    把一个「不存在的名字」换成替身，正是回退时能被抓到的原因。
    """
    monkeypatch.setattr(image_node, "short_db_session", _FakeSession, raising=False)
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _Boom(), raising=False)

    mid, att = uuid4(), uuid4()
    seen: list[tuple[str, object]] = []

    async def fake_resolve(db, ctx, *, model_config_id, agent_model=None, agent_config=None):
        assert model_config_id == mid
        seen.append(("resolve", db))
        return type("Model", (), {"id": mid, "name": "m"})()

    async def fake_generate(db, ctx, model, **kwargs):
        assert kwargs["purpose"] == PURPOSE_FLOW_GENERATED
        seen.append(("generate", db))
        return ImageGenerateResult(attachment_ids=[att], mime_type="image/png", media_asset_ids=[])

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_image_async=False,
        agent_config={},
        resolve_generative_image=fake_resolve,
        generate_image_sync=fake_generate,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}

    out = _run(image_node.image_generate(node, {}, ctx))

    assert out == {
        "kind": "image",
        "attachment_id": str(att),
        "attachment_ids": [str(att)],
        "mime_type": "image/png",
    }
    assert [kind for kind, _ in seen] == ["resolve", "generate"]
    assert all(isinstance(db, _FakeSession) for _, db in seen)


def test_video_generate_sync_never_falls_back_to_global_session(monkeypatch):
    """同步生视频站点：全局会话换成调用即炸替身，解析与编排仍必须走短会话。

    ``raising=False`` 是有意的：Task 1 之后本模块不再 import ``AsyncSessionLocal``，
    把一个「不存在的名字」换成替身，正是回退时能被抓到的原因。
    """
    monkeypatch.setattr(video_node, "short_db_session", _FakeSession, raising=False)
    monkeypatch.setattr(video_node, "AsyncSessionLocal", _Boom(), raising=False)

    mid, att = uuid4(), uuid4()
    seen: list[tuple[str, object]] = []

    async def fake_resolve(db, ctx, *, model_config_id, agent_config=None):
        assert model_config_id == mid
        seen.append(("resolve", db))
        return type("Model", (), {"id": mid, "name": "m"})()

    async def fake_generate(db, ctx, model, **kwargs):
        assert kwargs["purpose"] == PURPOSE_FLOW_GENERATED
        seen.append(("generate", db))
        return VideoGenerateResult(attachment_id=att, mime_type="video/mp4", duration_sec=5, media_asset_id=None)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_video_async=False,
        resolve_generative_video=fake_resolve,
        generate_video_sync=fake_generate,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}

    out = _run(video_node.video_generate(node, {}, ctx))

    assert out == {
        "kind": "video",
        "attachment_id": str(att),
        "mime_type": "video/mp4",
        "duration_sec": 5,
    }
    assert [kind for kind, _ in seen] == ["resolve", "generate"]
    assert all(isinstance(db, _FakeSession) for _, db in seen)
