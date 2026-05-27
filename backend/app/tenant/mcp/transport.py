"""
MCP 传输类型归一化（HTTP / SSE / STDIO / Custom）。

与 client 路由:
- http：Streamable HTTP JSON/SSE 响应
- sse：Legacy GET /sse + POST message；失败再降级
- stdio：占位，执行待沙箱 Runner
- custom：自定义协议适配器，通过 connection_config.adapter_url 转发 JSON-RPC

列表 Tab transport_filter_values 兼容历史数据 streamable-http。
"""


def normalize_transport(transport: str | None) -> str:
    """将 transport 别名归一化为 http / sse / stdio / custom。"""
    t = (transport or "sse").lower().strip()
    if t in ("http", "streamable-http"):
        return "http"
    if t == "stdio":
        return "stdio"
    if t == "custom":
        return "custom"
    return "sse"


def transport_filter_values(tab: str | None) -> list[str] | None:
    """列表 Tab 筛选值；http 兼容历史 streamable-http 存库值。"""
    if not tab or tab in ("all", ""):
        return None
    t = normalize_transport(tab)
    if t == "http":
        return ["http", "streamable-http"]
    if t in ("sse", "stdio", "custom"):
        return [t]
    return None
