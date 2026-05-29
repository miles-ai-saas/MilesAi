"""运营后台 Phase 2 角色与管理员治理测试。"""

from uuid import uuid4

import pytest

from app.admin.app_sys.deps import AdminContext, require_admin_role
from app.common.exceptions import BadRequestError, ForbiddenError


@pytest.mark.asyncio
async def test_require_admin_role_allows_super_admin():
    checker = require_admin_role("ops")
    ctx = AdminContext(admin_id=uuid4(), username="sa", role="super_admin")
    assert await checker(ctx=ctx) == ctx


@pytest.mark.asyncio
async def test_require_admin_role_allows_matching_role():
    checker = require_admin_role("ops")
    ctx = AdminContext(admin_id=uuid4(), username="ops1", role="ops")
    assert await checker(ctx=ctx) == ctx


@pytest.mark.asyncio
async def test_require_admin_role_denies_other_roles():
    checker = require_admin_role("ops")
    ctx = AdminContext(admin_id=uuid4(), username="bill", role="billing")
    with pytest.raises(ForbiddenError):
        await checker(ctx=ctx)


@pytest.mark.asyncio
async def test_admin_management_validate_role():
    from app.admin.app_ops.services.admins import AdminManagementService

    svc = AdminManagementService(db=None)  # type: ignore[arg-type]
    with pytest.raises(BadRequestError):
        svc._validate_role("unknown_role")
