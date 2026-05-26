"""
工具域：租户自定义工具、内置工具执行与 MCP。

- ``invoke/``：工具调用门面（``invoke_tool_with_context`` 等），见 ``invoke.__init__``。
- ``builtins/``：内置 slug 的 handler 注册表，由 ``invoke.builtin`` 分发。
- ``services/tools.py``：工具 CRUD API 用 Service。

约定见 ``backend/README.md`` § services/ 子包（按聚合拆分）。
"""
