"""
租户 MCP（Model Context Protocol）集成包。

分层
----
- **HTTP API**：``views.mcp`` → ``services.mcp.McpServiceManager``
- **远程协议**：``client`` / ``sse_transport`` / ``rpc`` / ``security``
- **与 Agent**：``tools_cache`` 经 ``tenant.agents.context`` 注入提示词；真 invoke 见工具页试调用

Phase：HTTP/SSE 已支持 sync + invoke；STDIO 入库待 Runner 沙箱（见 docs/architecture/mcp-sandbox.md）。
"""
