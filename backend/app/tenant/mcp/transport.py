"""
MCP 传输类型归一化（HTTP / SSE / STDIO）。

与 ``client`` 路由
----------------
- ``http``：Streamable HTTP JSON/SSE 响应（``streamable_http_json_rpc``）
- ``sse``：Legacy GET /sse + POST message；失败再降级 http 链
- ``stdio``：仅登记占位 ``stdio://``，执行待沙箱 Runner

列表 Tab ``transport_filter_values`` 兼容历史库里的 ``streamable-http`` 字面量。
"""


def normalize_transport(transport: str | None) -> str:
    """
    将库表/前端传入的 transport 归一为 http | sse | stdio。

    streamable-http 与 http 在实现上共用 Streamable HTTP 客户端。
    """
    t = (transport or "sse").lower().strip()
    if t in ("http", "streamable-http"):
        return "http"
    if t == "stdio":
        return "stdio"
    return "sse"


def transport_filter_values(tab: str | None) -> list[str] | None:
    """
    列表 API 的 Tab 筛选值。

    返回 None 表示「全部」；http Tab 需包含历史数据中的 streamable-http。
    """
    if not tab or tab in ("all", ""):
        return None
    t = normalize_transport(tab)
    if t == "http":
        return ["http", "streamable-http"]
    if t in ("sse", "stdio"):
        return [t]
    return None
