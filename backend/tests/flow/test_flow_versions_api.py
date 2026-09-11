"""流程版本列表与详情 service。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_core.models.flow import Flow, FlowStatus, FlowVersion
from miles_portal.tenant.flows.services.flow import FlowService


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
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="u",
        is_superuser=False,
        permissions=frozenset(["flow:read"]),
    )
    svc = FlowService(db, ctx)

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
