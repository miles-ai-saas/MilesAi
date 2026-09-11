"""Python 钩子插件测试。"""

import pytest

from miles_portal.tenant.hooks.plugins.echo import handle


@pytest.mark.asyncio
async def test_echo_python_hook():
    out = await handle({"event": "test"})
    assert out["action"] == "continue"
