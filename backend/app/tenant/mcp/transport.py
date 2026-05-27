"""
MCP 传输类型归一化（HTTP / SSE / STDIO / Custom）。

与 client 路由:
- http：Streamable HTTP JSON/SSE 响应
- sse：Legacy GET /sse + POST message；失败再降级
- stdio：占位，执行待沙箱 Runner
- custom：自定义协议适配器，通过 connection_config.adapter_url 转发 JSON-RPC

列表 Tab transport_filter_values 兼容历史数据 streamable-http。
"""

from app.tenant.mcp.constants import MCP_TRANSPORT_HTTP_LEGACY, McpTransport


def normalize_transport(transport: str | McpTransport | None) -> McpTransport:
    """将 transport 别名归一化为 ``McpTransport``。"""
    if isinstance(transport, McpTransport):
        return transport
    t = (transport or McpTransport.SSE.value).lower().strip()
    if t in (McpTransport.HTTP.value, MCP_TRANSPORT_HTTP_LEGACY):
        return McpTransport.HTTP
    if t == McpTransport.STDIO.value:
        return McpTransport.STDIO
    if t == McpTransport.CUSTOM.value:
        return McpTransport.CUSTOM
    return McpTransport.SSE


def transport_filter_values(tab: str | None) -> list[str] | None:
    """列表 Tab 筛选值；http 兼容历史 streamable-http 存库值。"""
    if not tab or tab in ("all", ""):
        return None
    t = normalize_transport(tab)
    if t == McpTransport.HTTP:
        return [McpTransport.HTTP.value, MCP_TRANSPORT_HTTP_LEGACY]
    if t in (McpTransport.SSE, McpTransport.STDIO, McpTransport.CUSTOM):
        return [t.value]
    return None
