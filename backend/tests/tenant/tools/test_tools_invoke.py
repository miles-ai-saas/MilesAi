import pytest

from app.tenant.tools.builtin_registry import BUILTIN_SLUGS
from app.tenant.tools.builtins.handlers import BUILTIN_HANDLERS
from app.tenant.tools.invoke import invoke_builtin, safe_calculate


def test_builtin_handlers_cover_registry():
    """registry 声明的 slug 与 handler 分发表必须一一对应。"""
    assert set(BUILTIN_HANDLERS) == BUILTIN_SLUGS


@pytest.mark.asyncio
async def test_get_current_datetime():
    out = await invoke_builtin("get_current_datetime", {}, db=None, ctx=None)
    assert "datetime" in out
    assert "T" in out["datetime"]
    assert out["timezone"] == "UTC"


def test_calculator():
    assert safe_calculate("1+2*3") == 7.0
