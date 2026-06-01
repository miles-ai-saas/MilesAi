"""知识库配额校验。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import ForbiddenError
from app.models.platform.tenant import Tenant
from app.tenant.kb.services.quota import assert_can_create_kb, assert_can_upload_bytes


@pytest.mark.asyncio
async def test_assert_can_create_kb_raises_when_at_limit():
    tenant_id = uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="t",
        max_knowledge_bases=2,
        max_storage_mb=1024,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)

    with patch(
        "app.tenant.kb.services.quota.count_knowledge_bases",
        new_callable=AsyncMock,
        return_value=2,
    ):
        with pytest.raises(ForbiddenError, match="知识库数量已达上限"):
            await assert_can_create_kb(db, tenant_id)


@pytest.mark.asyncio
async def test_assert_can_upload_bytes_raises_when_storage_full():
    tenant_id = uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="t",
        max_knowledge_bases=10,
        max_storage_mb=1,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)

    with (
        patch(
            "app.tenant.kb.services.quota.get_max_file_mb",
            new_callable=AsyncMock,
            return_value=50,
        ),
        patch(
            "app.tenant.kb.services.quota.sum_storage_bytes",
            new_callable=AsyncMock,
            return_value=1024 * 1024,
        ),
    ):
        with pytest.raises(ForbiddenError, match="存储空间不足"):
            await assert_can_upload_bytes(db, tenant_id, 1024)
