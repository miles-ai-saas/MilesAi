"""job_execution 画布 job 提交回调：构造 JobCreate 并委托 GenerativeJobService.submit_*。"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_portal.tenant.generative.services import job_execution


def _run(coro):
    return asyncio.run(coro)


class _FakeJobService:
    """替身 GenerativeJobService：记录入参，返回假 job（id 可用）。"""

    def __init__(self, db, ctx, *, submit_image=None, submit_video=None):
        self._db = db
        self._ctx = ctx
        self._submit_image = submit_image
        self._submit_video = submit_video

    async def submit_image(self, body, **kwargs):
        return await self._submit_image(self, body, kwargs)

    async def submit_video(self, body, **kwargs):
        return await self._submit_video(self, body, kwargs)


def _make_fake(job_id, captures):
    async def _submit_image(svc, body, kwargs):
        captures.append(("image", body, kwargs))
        return SimpleNamespace(id=job_id)

    async def _submit_video(svc, body, kwargs):
        captures.append(("video", body, kwargs))
        return SimpleNamespace(id=job_id)

    return _FakeJobService(None, None, submit_image=_submit_image, submit_video=_submit_video)


@pytest.fixture()
def fake_job_service(monkeypatch):
    import miles_portal.tenant.generative.services.job as job_module

    job_id = uuid4()
    captures = []
    # 回调内函数级 `from ...services.job import GenerativeJobService` 每次调用时
    # 读取 job 模块属性，故须 patch job 模块而非 job_execution
    monkeypatch.setattr(
        job_module,
        "GenerativeJobService",
        lambda db, ctx: _make_fake(job_id, captures),
    )
    return SimpleNamespace(job_id=job_id, captures=captures)


def _tenant_ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


def test_submit_generative_image_job_delegates(fake_job_service, monkeypatch):
    monkeypatch.setattr(job_execution, "get_trace_id", lambda: "trace-1")
    pid, mid, aid = uuid4(), uuid4(), uuid4()
    out_id = _run(
        job_execution.submit_generative_image_job(
            None,
            _tenant_ctx(),
            prompt="画猫",
            size="1024x1024",
            n=2,
            image_attachment_id=aid,
            model_config_id=mid,
            agent_id=pid,
            agent_config={"_k": "v"},
        )
    )
    assert out_id == fake_job_service.job_id
    (kind, body, kwargs) = fake_job_service.captures[0]
    assert kind == "image"
    assert body.prompt == "画猫"
    assert body.size == "1024x1024"
    assert body.n == 2
    assert body.image_attachment_id == aid
    assert body.model_config_id == mid
    assert kwargs["source"] == "flow_node"
    assert kwargs["agent_id"] == pid
    assert kwargs["agent_config"] == {"_k": "v"}
    assert kwargs["trace_id"] == "trace-1"


def test_submit_generative_video_job_delegates(fake_job_service, monkeypatch):
    monkeypatch.setattr(job_execution, "get_trace_id", lambda: "trace-2")
    pid, mid, first, last = uuid4(), uuid4(), uuid4(), uuid4()
    out_id = _run(
        job_execution.submit_generative_video_job(
            None,
            _tenant_ctx(),
            prompt="一段短片",
            duration=5,
            resolution="720P",
            image_attachment_id=first,
            last_frame_attachment_id=last,
            model_config_id=mid,
            agent_id=pid,
            agent_config=None,
        )
    )
    assert out_id == fake_job_service.job_id
    (kind, body, kwargs) = fake_job_service.captures[0]
    assert kind == "video"
    assert body.prompt == "一段短片"
    assert body.duration == 5
    assert body.resolution == "720P"
    assert body.image_attachment_id == first
    assert body.last_frame_attachment_id == last
    assert body.model_config_id == mid
    assert kwargs["source"] == "flow_node"
    assert kwargs["agent_id"] == pid
    assert kwargs["agent_config"] == {}
