"""业务中心项目服务单元测试（租户隔离与模板阶段）。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.schemas.project import BizWorkPackageCreate, BizWorkPackageUpdate
from app.biz.services.project import ProjectService
from app.common.exceptions import ForbiddenError, NotFoundError
from app.core.tenant import TenantContext
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_get_project_denies_other_tenant():
    tenant_a = uuid4()
    tenant_b = uuid4()
    project_id = uuid4()

    row = MagicMock()
    row.id = project_id
    row.tenant_id = tenant_b

    db = AsyncMock()
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_a,
        username="tester",
        is_superuser=False,
        permissions=frozenset(),
    )
    svc = ProjectService(db, ctx)
    svc.repo.get_by_id = AsyncMock(return_value=row)

    with pytest.raises(ForbiddenError):
        await svc.get_project(project_id)


@pytest.mark.asyncio
async def test_get_project_not_found():
    db = AsyncMock()
    svc = ProjectService(db, make_tenant_ctx())
    svc.repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await svc.get_project(uuid4())


@pytest.mark.asyncio
async def test_add_work_package_applies_service_line_template():
    tenant_id = uuid4()
    project_id = uuid4()
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="pm",
        is_superuser=True,
        permissions=frozenset(),
    )

    db = AsyncMock()
    svc = ProjectService(db, ctx)
    svc.template_svc.resolve_initial_stage = AsyncMock(return_value=("脚本", 0))

    body = BizWorkPackageCreate(service_line="video_production", name="主片剪辑")
    wp = await svc._add_work_package(project_id, body)

    assert wp.service_line == "video_production"
    assert wp.name == "主片剪辑"
    assert wp.stage == "脚本"
    assert wp.stage_index == 0
    svc.template_svc.resolve_initial_stage.assert_awaited_once_with(tenant_id, "video_production")
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_work_package_logs_status_change(monkeypatch):
    tenant_id = uuid4()
    base = make_tenant_ctx()
    ctx = TenantContext(
        user_id=base.user_id,
        tenant_id=tenant_id,
        username=base.username,
        is_superuser=True,
        permissions=base.permissions,
    )

    wp = MagicMock()
    wp.id = uuid4()
    wp.tenant_id = tenant_id
    wp.project_id = uuid4()
    wp.service_line = "event"
    wp.name = "执行"
    wp.stage = "方案"
    wp.stage_index = 0
    wp.status = "pending"
    wp.owner_id = None
    wp.budget = None
    wp.actual_cost = None
    wp.planned_start = None
    wp.planned_end = None

    db = AsyncMock()
    svc = ProjectService(db, ctx)
    svc.repo.get_work_package = AsyncMock(return_value=wp)

    audit_mock = AsyncMock()
    monkeypatch.setattr("app.biz.services.project.log_biz_action", audit_mock)

    await svc.update_work_package(wp.id, BizWorkPackageUpdate(status="in_progress"))

    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["action"] == "biz.work_package.status_change"
    assert wp.status == "in_progress"
