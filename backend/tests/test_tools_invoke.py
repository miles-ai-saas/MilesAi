import pytest

from app.tenant.tools.invoke import invoke_builtin, safe_calculate


@pytest.mark.asyncio
async def test_get_current_datetime():
    out = await invoke_builtin("get_current_datetime", {}, db=None, ctx=None)
    assert "datetime" in out
    assert "T" in out["datetime"]
    assert out["timezone"] == "UTC"


def test_calculator():
    assert safe_calculate("1+2*3") == 7.0
