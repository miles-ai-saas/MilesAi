"""流程版本列表与详情 / 一键恢复 service。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.models.flow import Flow, FlowStatus, FlowVersion
from miles_core.tenant import TenantContext
from miles_portal.tenant.flows.schemas.flow import FlowRestoreVersion
from miles_portal.tenant.flows.services.flow import FlowService


def _ctx(tenant_id):
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="u",
        is_superuser=False,
        permissions=frozenset(["flow:read", "flow:write"]),
    )


@pytest.mark.asyncio
async def test_list_versions(monkeypatch):
    flow_id = uuid4()
    tenant_id = uuid4()
    flow = Flow(
        id=flow_id,
        tenant_id=tenant_id,
        name="t",
        status=FlowStatus.DRAFT,
        current_version=2,
    )
    now = datetime.now(UTC)
    v2 = FlowVersion(
        id=uuid4(),
        flow_id=flow_id,
        version=2,
        graph_json={"nodes": [], "edges": []},
        remark="latest",
        created_at=now,
    )
    v1 = FlowVersion(
        id=uuid4(),
        flow_id=flow_id,
        version=1,
        graph_json={"nodes": [], "edges": []},
        remark="init",
        created_at=now,
    )

    db = AsyncMock()
    svc = FlowService(db, _ctx(tenant_id))

    async def _get_flow(_fid):
        return flow

    async def _list_versions(_fid):
        return [v2, v1]

    monkeypatch.setattr(svc, "_get_flow_or_raise", _get_flow)
    svc.repo.list_versions = AsyncMock(side_effect=_list_versions)

    items = await svc.list_versions(flow_id)
    assert len(items) == 2
    assert items[0].version == 2
    assert items[1].version == 1


@pytest.mark.asyncio
async def test_restore_version_copies_graph_as_new_version(monkeypatch):
    flow_id = uuid4()
    tenant_id = uuid4()
    flow = Flow(
        id=flow_id,
        tenant_id=tenant_id,
        name="t",
        status=FlowStatus.PUBLISHED,
        current_version=2,
    )
    now = datetime.now(UTC)
    v1_graph = {"nodes": [{"id": "a"}], "edges": []}
    v1 = FlowVersion(
        id=uuid4(),
        flow_id=flow_id,
        version=1,
        graph_json=v1_graph,
        remark="init",
        created_at=now,
    )
    created = FlowVersion(
        id=uuid4(),
        flow_id=flow_id,
        version=3,
        graph_json=v1_graph,
        remark="恢复自 v1",
        created_at=now,
        editor_id=uuid4(),
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    svc = FlowService(db, _ctx(tenant_id))

    monkeypatch.setattr(svc, "_get_flow_or_raise", AsyncMock(return_value=flow))
    svc.repo.get_version = AsyncMock(return_value=v1)
    svc.version_repo.create = AsyncMock(return_value=created)

    out = await svc.restore_version(flow_id, 1)

    assert out.version == 3
    assert out.remark == "恢复自 v1"
    assert flow.current_version == 3
    svc.version_repo.create.assert_awaited()
    call_kw = svc.version_repo.create.await_args.kwargs
    assert call_kw["version"] == 3
    assert call_kw["graph_json"] == v1_graph
    assert call_kw["remark"] == "恢复自 v1"


@pytest.mark.asyncio
async def test_restore_current_version_rejected(monkeypatch):
    flow_id = uuid4()
    tenant_id = uuid4()
    flow = Flow(
        id=flow_id,
        tenant_id=tenant_id,
        name="t",
        status=FlowStatus.DRAFT,
        current_version=2,
    )
    svc = FlowService(AsyncMock(), _ctx(tenant_id))
    monkeypatch.setattr(svc, "_get_flow_or_raise", AsyncMock(return_value=flow))
    with pytest.raises(BadRequestError, match="当前版本"):
        await svc.restore_version(flow_id, 2)


@pytest.mark.asyncio
async def test_restore_missing_version(monkeypatch):
    flow_id = uuid4()
    tenant_id = uuid4()
    flow = Flow(
        id=flow_id,
        tenant_id=tenant_id,
        name="t",
        status=FlowStatus.DRAFT,
        current_version=2,
    )
    svc = FlowService(AsyncMock(), _ctx(tenant_id))
    monkeypatch.setattr(svc, "_get_flow_or_raise", AsyncMock(return_value=flow))
    svc.repo.get_version = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await svc.restore_version(flow_id, 1, FlowRestoreVersion())
