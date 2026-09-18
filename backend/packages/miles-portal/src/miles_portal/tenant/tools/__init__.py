"""
工具域：租户自定义工具、内置工具执行与 MCP。

三个「内置」相关名字各指一事，勿混：
- ``builtin_registry.py``：声明表（``BUILTIN_REGISTRY`` / ``BUILTIN_SLUGS`` / ``get_builtin``）；
- ``handlers/``：各内置工具的 handler 实现；
- ``invoke/builtin.py``：按 slug 分发到 ``handlers.BUILTIN_HANDLERS``。

其余：
- ``invoke/``：工具调用门面（``invoke_tool_with_context`` 等），见 ``invoke.__init__``。
- ``primitives.py``：与「内置/自定义」无关的纯函数（``safe_calculate``、``apply_template``）。
- ``services/tools.py``：工具 CRUD API 用 Service。
- ``services/agent_tool_assembly.py``：把自定义 + MCP + 内置装配为对话工具 schema。

约定见 ``backend/README.md`` § services/ 子包（按聚合拆分）。
"""
