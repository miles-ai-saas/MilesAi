"""
Invoke 聚合：内置与自定义工具执行（确认策略、Hook、调用日志）。

目录职责
--------
- ``context.py``：``invoke_tool_with_context``（对外主入口）、``invoke_tool_by_name``。
- ``builtin.py``：按 slug 分发至 ``tenant.tools.handlers.handlers``。
- ``custom.py``：租户 HTTP / 脚本工具。

不在此包内
----------
``tenant.tools.handlers/``：各内置工具的 handler 实现（``calculator``、``generate_image`` 等）。

无 ``XxxService`` 类；为纯函数 + 门面 re-export。对外::

    from miles_portal.tenant.tools.invoke import invoke_tool_with_context, safe_calculate
"""

from miles_portal.tenant.tools.invoke.builtin import invoke_builtin
from miles_portal.tenant.tools.invoke.context import (
    invoke_tool_by_name,
    invoke_tool_with_context,
    resolve_bound_skill_id_from_agent,
)
from miles_portal.tenant.tools.invoke.custom import (
    SCRIPT_RUNNER_DISABLED,
    invoke_custom_http,
    invoke_custom_script,
)
from miles_portal.tenant.tools.primitives import safe_calculate

__all__ = [
    "SCRIPT_RUNNER_DISABLED",
    "invoke_builtin",
    "invoke_custom_http",
    "invoke_custom_script",
    "invoke_tool_by_name",
    "invoke_tool_with_context",
    "resolve_bound_skill_id_from_agent",
    "safe_calculate",
]
