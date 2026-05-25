"""工具 catalog source 校验（不依赖 DB）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import BadRequestError
from app.tenant.tools.services.tools import ToolsService


@pytest.mark.asyncio
async def test_list_catalog_rejects_mcp_source():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
    ctx = MagicMock(tenant_id="00000000-0000-0000-0000-000000000001")
    svc = ToolsService(db, ctx)
    with pytest.raises(BadRequestError, match="builtin"):
        await svc.list_catalog(source="mcp")
