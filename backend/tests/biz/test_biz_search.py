"""业务中心全局搜索单元测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.biz.services.search import BizSearchService
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_search_empty_query_returns_no_items():
    ctx = make_tenant_ctx()
    db = AsyncMock()
    svc = BizSearchService(db, ctx)

    out = await svc.search("")
    assert out.query == ""
    assert out.items == []
    db.scalars.assert_not_called()


@pytest.mark.asyncio
async def test_search_whitespace_only_returns_no_items():
    ctx = make_tenant_ctx()
    db = AsyncMock()
    svc = BizSearchService(db, ctx)

    out = await svc.search("   ")
    assert out.query == ""
    assert out.items == []


@pytest.mark.asyncio
async def test_search_maps_client_hits():
    ctx = make_tenant_ctx()
    client = MagicMock()
    client.id = "c1"
    client.name = "星火传媒"
    client.short_name = "星火"

    db = AsyncMock()
    db.scalars = AsyncMock(side_effect=[
        MagicMock(__iter__=lambda s: iter([client])),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ])
    db.execute = AsyncMock(return_value=MagicMock(__iter__=lambda s: iter([])))

    svc = BizSearchService(db, ctx)
    out = await svc.search("星火", limit=12)

    assert out.query == "星火"
    assert len(out.items) == 1
    assert out.items[0].kind == "client"
    assert out.items[0].title == "星火传媒"
    assert out.items[0].subtitle == "星火"
