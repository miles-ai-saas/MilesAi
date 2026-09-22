"""流程标签绑定 service 行为。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_core.models.flow import Flow, FlowStatus
from miles_core.models.meta.tag import TagEntityType
from miles_core.tenant import TenantContext
from miles_portal.tenant.flows.schemas.flow import FlowCreate, FlowUpdate
from miles_portal.tenant.flows.services.flow import FlowService
from miles_portal.tenant.tags.schemas.tag import TagRefOut


@pytest.mark.asyncio
async def test_create_flow_with_tags(monkeypatch):
    tenant_id = uuid4()
    flow_id = uuid4()
    tag_id = uuid4()
    now = datetime.now(UTC)
    flow = Flow(
        id=flow_id,
        tenant_id=tenant_id,
        name="RAG",
        description="desc",
        status=FlowStatus.DRAFT,
        current_version=1,
        created_at=now,
    )

    db = AsyncMock()
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="u",
        is_superuser=False,
        permissions=frozenset(["flow:write"]),
    )
    svc = FlowService(db, ctx)
    svc.repo.create = AsyncMock(return_value=flow)
    svc._save_version = AsyncMock()
    replace = AsyncMock()
    get_refs = AsyncMock(return_value={flow_id: [TagRefOut(id=tag_id, name="客服", slug="kefu")]})
    monkeypatch.setattr(
        "miles_portal.tenant.flows.services.flow.TagService.replace_entity_tags",
        replace,
    )
    monkeypatch.setattr(
        "miles_portal.tenant.flows.services.flow.TagService.get_refs_map",
        get_refs,
    )
    monkeypatch.setattr(
        "miles_portal.tenant.system.services.quota.assert_can_create_flow",
        AsyncMock(),
    )

    out = await svc.create_flow(FlowCreate(name="RAG", description="desc", tag_ids=[tag_id], graph_json={"nodes": [], "edges": []}))

    replace.assert_awaited_once_with(TagEntityType.FLOW, flow_id, [tag_id])
    assert out.tags[0].slug == "kefu"


@pytest.mark.asyncio
async def test_update_flow_replaces_tags(monkeypatch):
    tenant_id = uuid4()
    flow_id = uuid4()
    tag_id = uuid4()
    now = datetime.now(UTC)
    flow = Flow(
        id=flow_id,
        tenant_id=tenant_id,
        name="RAG",
        status=FlowStatus.DRAFT,
        current_version=1,
        created_at=now,
    )

    db = AsyncMock()
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="u",
        is_superuser=False,
        permissions=frozenset(["flow:write"]),
    )
    svc = FlowService(db, ctx)
    monkeypatch.setattr(svc, "_get_flow_or_raise", AsyncMock(return_value=flow))
    svc.repo.update_fields = AsyncMock()
    replace = AsyncMock()
    get_refs = AsyncMock(return_value={flow_id: []})
    monkeypatch.setattr(
        "miles_portal.tenant.flows.services.flow.TagService.replace_entity_tags",
        replace,
    )
    monkeypatch.setattr(
        "miles_portal.tenant.flows.services.flow.TagService.get_refs_map",
        get_refs,
    )

    await svc.update_flow(flow_id, FlowUpdate(tag_ids=[tag_id]))

    replace.assert_awaited_once_with(TagEntityType.FLOW, flow_id, [tag_id])
