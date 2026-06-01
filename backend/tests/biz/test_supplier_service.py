"""供应商服务单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.services.supplier import SupplierService
from app.common.exceptions import ForbiddenError, NotFoundError
from app.core.tenant import TenantContext
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_get_supplier_denies_other_tenant():
    tenant_a = uuid4()
    tenant_b = uuid4()
    supplier_id = uuid4()

    row = MagicMock()
    row.id = supplier_id
    row.tenant_id = tenant_b

    db = AsyncMock()
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_a,
        username="tester",
        is_superuser=False,
        permissions=frozenset(),
    )
    svc = SupplierService(db, ctx)
    svc.repo.get_by_id = AsyncMock(return_value=row)

    with pytest.raises(ForbiddenError):
        await svc.get_supplier(supplier_id)


@pytest.mark.asyncio
async def test_get_supplier_not_found():
    db = AsyncMock()
    svc = SupplierService(db, make_tenant_ctx())
    svc.repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await svc.get_supplier(uuid4())
