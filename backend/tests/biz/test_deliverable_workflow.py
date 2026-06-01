"""交付物提交/验收/驳回单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.services.deliverable import DeliverableService
from app.common.exceptions import BadRequestError
from tests.conftest import make_tenant_ctx


def _make_deliverable(*, status: str = "draft"):
    row = MagicMock()
    row.id = uuid4()
    row.tenant_id = make_tenant_ctx().tenant_id
    row.project_id = uuid4()
    row.name = "方案稿"
    row.type = "document"
    row.status = status
    row.work_package_id = None
    row.attachment_id = None
    row.media_asset_id = None
    row.version = "v1"
    row.submitted_at = None
    row.accepted_at = None
    return row


@pytest.mark.asyncio
async def test_submit_deliverable_success(monkeypatch):
    ctx = make_tenant_ctx()
    row = _make_deliverable(status="draft")
    db = AsyncMock()
    svc = DeliverableService(db, ctx)
    svc.repo.get_by_id = AsyncMock(return_value=row)
    audit = AsyncMock()
    monkeypatch.setattr("app.biz.services.deliverable.log_biz_action", audit)

    out = await svc.submit(row.id)
    assert out.status == "submitted"
    assert row.status == "submitted"
    assert row.submitted_at
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_deliverable_invalid_status():
    ctx = make_tenant_ctx()
    row = _make_deliverable(status="accepted")
    db = AsyncMock()
    svc = DeliverableService(db, ctx)
    svc.repo.get_by_id = AsyncMock(return_value=row)

    with pytest.raises(BadRequestError, match="草稿或已驳回"):
        await svc.submit(row.id)


@pytest.mark.asyncio
async def test_accept_deliverable_success(monkeypatch):
    ctx = make_tenant_ctx()
    row = _make_deliverable(status="submitted")
    db = AsyncMock()
    svc = DeliverableService(db, ctx)
    svc.repo.get_by_id = AsyncMock(return_value=row)
    audit = AsyncMock()
    monkeypatch.setattr("app.biz.services.deliverable.log_biz_action", audit)

    out = await svc.accept(row.id)
    assert out.status == "accepted"
    assert row.accepted_at
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reject_deliverable_success(monkeypatch):
    ctx = make_tenant_ctx()
    row = _make_deliverable(status="submitted")
    row.accepted_at = "2026-01-01T00:00:00Z"
    db = AsyncMock()
    svc = DeliverableService(db, ctx)
    svc.repo.get_by_id = AsyncMock(return_value=row)
    audit = AsyncMock()
    monkeypatch.setattr("app.biz.services.deliverable.log_biz_action", audit)

    out = await svc.reject(row.id)
    assert out.status == "rejected"
    assert row.accepted_at is None
    audit.assert_awaited_once()
