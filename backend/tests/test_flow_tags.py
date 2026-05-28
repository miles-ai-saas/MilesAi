"""流程标签绑定 service 行为。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.tenant import TenantContext
from app.models.flow import Flow, FlowStatus
from app.models.tag import TagEntityType
from app.tenant.flows.schemas.flow import FlowCreate, FlowUpdate
from app.tenant.flows.services.flow import FlowService
from app.tenant.tags.schemas.tag import TagRefOut


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
        "app.tenant.flows.services.flow.TagService.replace_entity_tags",
        replace,
    )
    monkeypatch.setattr(
        "app.tenant.flows.services.flow.TagService.get_refs_map",
        get_refs,
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
        "app.tenant.flows.services.flow.TagService.replace_entity_tags",
        replace,
    )
    monkeypatch.setattr(
        "app.tenant.flows.services.flow.TagService.get_refs_map",
        get_refs,
    )

    await svc.update_flow(flow_id, FlowUpdate(tag_ids=[tag_id]))

    replace.assert_awaited_once_with(TagEntityType.FLOW, flow_id, [tag_id])
