"""工具 catalog source 校验（不依赖 DB）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.tools.schemas.tools import ToolInvokeRequest
from miles_portal.tenant.tools.services import tools as tools_mod
from miles_portal.tenant.tools.services.tools import ToolsService

_CTX = MagicMock(tenant_id="00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_list_catalog_rejects_mcp_source():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
    ctx = MagicMock(tenant_id="00000000-0000-0000-0000-000000000001")
    svc = ToolsService(db, ctx)
    with pytest.raises(BadRequestError, match="builtin"):
        await svc.list_catalog(source="mcp")


@pytest.mark.asyncio
async def test_trial_invoke_shares_one_meta_between_response_and_execution(monkeypatch):
    """试调用的响应 ``source`` 与执行所用 meta 必须同源，且判据只跑一次。

    旧实现是「响应按名字猜一次、执行再猜一次」（两套判据）；本条钉住收敛后的性质：
    ``resolve_tool_meta`` 只调用一次，结果原样透传给 ``invoke_tool_with_context``。
    """
    seen: dict = {}

    async def fake_resolve(db, ctx, name, *, tool_id=None):  # noqa: ANN001
        seen["resolve_calls"] = seen.get("resolve_calls", 0) + 1
        return {"slug": name, "name": "远端搜索", "description": None, "source": "mcp", "require_confirmation": False, "tool_id": None}

    async def fake_invoke_with_context(db, ctx, name, params, **kwargs):  # noqa: ANN001
        seen["meta"] = kwargs.get("meta")
        return {"ok": True}

    monkeypatch.setattr(tools_mod, "resolve_tool_meta", fake_resolve)
    monkeypatch.setattr(tools_mod, "invoke_tool_with_context", fake_invoke_with_context)

    result = await ToolsService(AsyncMock(), _CTX).invoke("mcp__x__y", ToolInvokeRequest(params={}))

    assert result.source == "mcp"
    assert seen["resolve_calls"] == 1, "判据只应跑一次"
    assert seen["meta"] is not None and seen["meta"]["source"] == result.source, "响应 source 必须取自执行所用的同一份 meta"
