"""内置 run_flow_once：仅已发布流程、递归深度护栏、超时夹取与执行委托。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError, NotFoundError
from app.models.flow import FlowStatus
from app.tenant.flows.schemas.flow import FlowRunResponse
from app.tenant.tools.services import flow_once


def _ctx(tenant_id=None) -> SimpleNamespace:
    return SimpleNamespace(tenant_id=tenant_id or uuid4(), is_superuser=False, permissions=frozenset())


def _patch_flow_repo(monkeypatch, flow) -> None:
    class _Repo:
        def __init__(self, db) -> None:  # noqa: ARG002
            pass

        async def get_by_id(self, flow_id):  # noqa: ARG002
            return flow

    monkeypatch.setattr("app.tenant.flows.repositories.flow.FlowRepository", _Repo)


def _published_flow(tenant_id):
    return SimpleNamespace(id=uuid4(), tenant_id=tenant_id, status=FlowStatus.PUBLISHED, current_version=2)


# --- 参数与护栏 ---


async def test_missing_flow_id_rejected():
    with pytest.raises(BadRequestError, match="flow_id"):
        await flow_once.run_published_flow_once(object(), _ctx(), flow_id=None)


async def test_depth_guard_blocks_recursion():
    token = flow_once._depth.set(flow_once.MAX_FLOW_ONCE_DEPTH)
    try:
        with pytest.raises(BadRequestError, match="嵌套触发"):
            await flow_once.run_published_flow_once(object(), _ctx(), flow_id=uuid4())
    finally:
        flow_once._depth.reset(token)


async def test_draft_flow_rejected(monkeypatch):
    tenant_id = uuid4()
    _patch_flow_repo(monkeypatch, SimpleNamespace(id=uuid4(), tenant_id=tenant_id, status=FlowStatus.DRAFT, current_version=1))
    with pytest.raises(BadRequestError, match="已发布"):
        await flow_once.run_published_flow_once(object(), _ctx(tenant_id), flow_id=uuid4())


async def test_unpublished_zero_version_rejected(monkeypatch):
    tenant_id = uuid4()
    _patch_flow_repo(monkeypatch, SimpleNamespace(id=uuid4(), tenant_id=tenant_id, status=FlowStatus.PUBLISHED, current_version=0))
    with pytest.raises(BadRequestError, match="已发布"):
        await flow_once.run_published_flow_once(object(), _ctx(tenant_id), flow_id=uuid4(), inputs={"query": "hi"})


async def test_missing_query_rejected(monkeypatch):
    tenant_id = uuid4()
    flow = _published_flow(tenant_id)
    _patch_flow_repo(monkeypatch, flow)
    with pytest.raises(BadRequestError, match="query"):
        await flow_once.run_published_flow_once(object(), _ctx(tenant_id), flow_id=flow.id, inputs={})


async def test_missing_flow_raises_not_found(monkeypatch):
    _patch_flow_repo(monkeypatch, None)
    with pytest.raises(NotFoundError):
        await flow_once.run_published_flow_once(object(), _ctx(), flow_id=uuid4())


# --- 执行委托 ---


async def test_runs_published_flow_and_shapes_output(monkeypatch):
    tenant_id = uuid4()
    flow = _published_flow(tenant_id)
    _patch_flow_repo(monkeypatch, flow)

    calls: dict = {}

    class _Service:
        def __init__(self, db, ctx) -> None:  # noqa: ARG002
            pass

        async def run(self, flow_id, body):
            calls.update({"flow_id": flow_id, "inputs": body.inputs})
            return FlowRunResponse(output="流程结果", steps=[{"node": "TextOutput"}])

    monkeypatch.setattr("app.tenant.flows.services.flow.FlowService", _Service)

    out = await flow_once.run_published_flow_once(
        object(),
        _ctx(tenant_id),
        flow_id=flow.id,
        inputs={"query": "hi"},
    )
    assert out == {"flow_id": str(flow.id), "output": "流程结果", "step_count": 1}
    assert calls == {"flow_id": flow.id, "inputs": {"query": "hi"}}


async def test_timeout_is_clamped_and_maps_to_bad_request(monkeypatch):
    import asyncio

    tenant_id = uuid4()
    flow = _published_flow(tenant_id)
    _patch_flow_repo(monkeypatch, flow)

    seen: dict = {}

    class _Service:
        def __init__(self, db, ctx) -> None:  # noqa: ARG002
            pass

        async def run(self, flow_id, body):  # noqa: ARG002
            await asyncio.sleep(5)
            return FlowRunResponse(output="late")

    monkeypatch.setattr("app.tenant.flows.services.flow.FlowService", _Service)

    async def fake_wait_for(coro, *, timeout):
        seen["timeout"] = timeout
        coro.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(flow_once.asyncio, "wait_for", fake_wait_for)

    with pytest.raises(BadRequestError, match="超时"):
        await flow_once.run_published_flow_once(object(), _ctx(tenant_id), flow_id=flow.id, inputs={"query": "hi"}, timeout_sec=9999)
    assert seen["timeout"] == flow_once.MAX_TIMEOUT_SEC
