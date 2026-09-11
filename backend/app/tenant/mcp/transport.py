"""
MCP 传输类型归一化（HTTP / SSE / STDIO / Custom）。

与 client 路由:
- http：Streamable HTTP JSON/SSE 响应
- sse：Legacy GET /sse + POST message；失败再降级
- stdio：占位，执行待沙箱 Runner
- custom：自定义协议适配器，通过 connection_config.adapter_url 转发 JSON-RPC
"""

from app.exec.mcp.constants import McpTransport


def normalize_transport(transport: str | McpTransport | None) -> McpTransport:
    """将 transport 字符串归一化为 ``McpTransport``。"""
    if isinstance(transport, McpTransport):
        return transport
    t = (transport or McpTransport.SSE.value).lower().strip()
    if t == McpTransport.HTTP.value:
        return McpTransport.HTTP
    if t == McpTransport.STDIO.value:
        return McpTransport.STDIO
    if t == McpTransport.CUSTOM.value:
        return McpTransport.CUSTOM
    return McpTransport.SSE


def transport_filter_values(tab: str | None) -> list[str] | None:
    """列表 Tab 筛选值。"""
    if not tab or tab in ("all", ""):
        return None
    t = normalize_transport(tab)
    return [t.value]
