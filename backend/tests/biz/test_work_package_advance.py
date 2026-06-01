"""工作包阶段推进单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.services.project import ProjectService
from app.common.exceptions import BadRequestError
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_advance_work_package_stage_success(monkeypatch):
    ctx = make_tenant_ctx()
    tenant_id = ctx.tenant_id

    wp = MagicMock()
    wp.id = uuid4()
    wp.tenant_id = tenant_id
    wp.project_id = uuid4()
    wp.service_line = "exhibition"
    wp.stage = "概念设计"
    wp.stage_index = 0
    wp.name = "主包"
    wp.status = "in_progress"
    wp.owner_id = None
    wp.budget = None
    wp.actual_cost = None
    wp.planned_start = None
    wp.planned_end = None

    db = AsyncMock()
    svc = ProjectService(db, ctx)
    svc.repo.get_work_package = AsyncMock(return_value=wp)
    svc.template_svc.next_stage = AsyncMock(return_value=("深化设计", 1))

    audit = AsyncMock()
    monkeypatch.setattr("app.biz.services.project.log_biz_action", audit)

    out = await svc.advance_work_package_stage(wp.id)
    assert out.stage == "深化设计"
    assert out.stage_index == 1
    assert wp.stage == "深化设计"
    assert wp.stage_index == 1
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_advance_work_package_stage_at_last_stage():
    ctx = make_tenant_ctx()
    tenant_id = ctx.tenant_id

    wp = MagicMock()
    wp.id = uuid4()
    wp.tenant_id = tenant_id
    wp.service_line = "exhibition"
    wp.stage_index = 5

    db = AsyncMock()
    svc = ProjectService(db, ctx)
    svc.repo.get_work_package = AsyncMock(return_value=wp)
    svc.template_svc.next_stage = AsyncMock(return_value=None)

    with pytest.raises(BadRequestError, match="最后阶段"):
        await svc.advance_work_package_stage(wp.id)
