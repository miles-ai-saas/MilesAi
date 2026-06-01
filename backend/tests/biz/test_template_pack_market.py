"""服务线模板市场单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.schemas.service_line_template import BizServiceLineTemplateOut
from app.biz.services.template_pack_market import ServiceLineTemplatePackMarketService
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_apply_pack_upserts_tenant_template(monkeypatch):
    ctx = make_tenant_ctx()
    db = AsyncMock()
    pack_id = uuid4()

    pack = MagicMock()
    pack.id = pack_id
    pack.service_line = "event"
    pack.name = "小型沙龙版"
    pack.stages = ["方案", "执行", "复盘"]
    pack.ai_config = {"agent_tag": "biz-event"}
    pack.install_count = 5

    svc = ServiceLineTemplatePackMarketService(db, ctx)
    svc.repo.get_catalog_pack = AsyncMock(return_value=pack)

    expected = BizServiceLineTemplateOut(
        service_line="event",
        label="活动策划",
        stages=["方案", "执行", "复盘"],
        source="tenant",
    )
    admin_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.biz.services.template_pack_market.ServiceLineTemplateAdminService.upsert",
        admin_mock,
    )

    result = await svc.apply_pack(pack_id)

    assert result.pack_name == "小型沙龙版"
    assert result.service_line == "event"
    assert result.template.source == "tenant"
    assert pack.install_count == 6
    admin_mock.assert_awaited_once()
