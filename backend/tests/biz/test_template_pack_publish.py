"""租户发布服务线模板包单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.schemas.template_pack import BizServiceLineTemplatePackCreate
from app.biz.services.template_pack_publish import ServiceLineTemplatePackPublishService
from app.models.biz.template_pack_status import TemplatePackStatus
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_submit_moves_draft_to_pending(monkeypatch):
    ctx = make_tenant_ctx()
    db = AsyncMock()
    pack_id = uuid4()

    row = MagicMock()
    row.id = pack_id
    row.tenant_id = ctx.tenant_id
    row.service_line = "event"
    row.name = "测试模板"
    row.stages = ["方案", "执行"]
    row.ai_config = {}
    row.status = TemplatePackStatus.DRAFT.value
    row.tags = []
    row.description = None
    row.publisher_name = "租户A"
    row.publisher_type = "tenant"
    row.is_featured = False
    row.install_count = 0
    row.review_note = None
    row.submitted_at = None
    row.reviewed_at = None

    svc = ServiceLineTemplatePackPublishService(db, ctx)
    svc.repo.get_mine = AsyncMock(return_value=row)
    db.refresh = AsyncMock()

    out = await svc.submit(pack_id)

    assert row.status == TemplatePackStatus.PENDING_REVIEW.value
    assert row.submitted_at is not None
    assert out.status == TemplatePackStatus.PENDING_REVIEW.value


@pytest.mark.asyncio
async def test_create_from_template_requires_stages(monkeypatch):
    ctx = make_tenant_ctx()
    db = AsyncMock()
    svc = ServiceLineTemplatePackPublishService(db, ctx)

    from app.biz.schemas.service_line_template import BizServiceLineTemplateOut

    monkeypatch.setattr(
        "app.biz.services.template_pack_publish.ServiceLineTemplateAdminService.list_templates",
        AsyncMock(return_value=[
            BizServiceLineTemplateOut(service_line="event", label="活动策划", stages=[], source="none"),
        ]),
    )

    with pytest.raises(Exception) as exc:
        await svc.create_from_template(BizServiceLineTemplatePackCreate(service_line="event", name="我的模板"))
    assert "阶段" in str(exc.value)


@pytest.mark.asyncio
async def test_update_mine_stages_after_reject():
    ctx = make_tenant_ctx()
    db = AsyncMock()
    pack_id = uuid4()

    row = MagicMock()
    row.id = pack_id
    row.tenant_id = ctx.tenant_id
    row.service_line = "event"
    row.name = "旧名"
    row.stages = ["方案"]
    row.ai_config = {}
    row.status = TemplatePackStatus.REJECTED.value
    row.tags = []
    row.description = None
    row.publisher_name = "租户"
    row.publisher_type = "tenant"
    row.is_featured = False
    row.is_active = True
    row.install_count = 0
    row.review_note = "阶段过少"
    row.submitted_at = None
    row.reviewed_at = None

    svc = ServiceLineTemplatePackPublishService(db, ctx)
    svc.repo.get_mine = AsyncMock(return_value=row)
    db.refresh = AsyncMock()

    from app.biz.schemas.template_pack import BizServiceLineTemplatePackUpdate

    out = await svc.update_mine(
        pack_id,
        BizServiceLineTemplatePackUpdate(stages=["方案", "执行", "复盘"], name="新名"),
    )

    assert row.stages == ["方案", "执行", "复盘"]
    assert row.name == "新名"
    assert out.name == "新名"
