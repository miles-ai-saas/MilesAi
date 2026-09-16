"""**临时**再导出层：``toolkit/`` 拆分期间保持既有 import 路径可用，随 Task 3 一并删除。

本模块不得新增任何逻辑；所有符号归属见同目录 ``toolkit/`` 各模块。
"""

from __future__ import annotations

from .toolkit.catalog import (
    build_platform_tools,
    build_stub_tool,
    get_generative_tools,
    get_platform_tools,
    get_skill_bound_tools,
    make_builtin_tool,
    make_custom_http_tool,
    make_custom_script_tool,
    make_mcp_tool,
    select_opt_in_builtin_tools,
)
from .toolkit.naming import (
    MCP_FUNCTION_PREFIX,
    compose_mcp_tool_name,
    is_mcp_tool_name,
    sanitize_ident,
    select_agent_tools,
)
from .toolkit.specs import CustomToolSpec, McpToolSpec, json_schema_to_pydantic, mcp_param_alias

# 转发壳自身不使用这些 import：实测不列 `__all__` 时 F401 会把 19 个符号全部报错，
# 其中 `build_platform_tools` 等确有调用点——F401 只看本文件，故此处显式声明再导出清单。
__all__ = [
    "MCP_FUNCTION_PREFIX",
    "CustomToolSpec",
    "McpToolSpec",
    "build_platform_tools",
    "build_stub_tool",
    "compose_mcp_tool_name",
    "get_generative_tools",
    "get_platform_tools",
    "get_skill_bound_tools",
    "is_mcp_tool_name",
    "json_schema_to_pydantic",
    "make_builtin_tool",
    "make_custom_http_tool",
    "make_custom_script_tool",
    "make_mcp_tool",
    "mcp_param_alias",
    "sanitize_ident",
    "select_agent_tools",
    "select_opt_in_builtin_tools",
]
