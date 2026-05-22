"""MCP 工具列表同步（JSON-RPC tools/list + HTTP 降级）。"""

import httpx


def _normalize_tools(raw: list | dict) -> list[dict]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and "tools" in raw:
        items = raw["tools"]
    else:
        return []
    out: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id") or "tool"
            desc = item.get("description") or item.get("summary") or ""
            out.append({"name": str(name), "description": str(desc)})
        elif isinstance(item, str):
            out.append({"name": item, "description": ""})
    return out


async def fetch_mcp_tools(endpoint_url: str, transport: str = "sse") -> list[dict]:
    """尝试 JSON-RPC，失败则 GET JSON，最后返回占位工具。"""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    rpc_body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if transport in ("http", "streamable-http", "sse"):
                resp = await client.post(endpoint_url, json=rpc_body, headers=headers)
                if resp.is_success:
                    data = resp.json()
                    if isinstance(data, dict) and "result" in data:
                        result = data["result"]
                        if isinstance(result, dict) and "tools" in result:
                            tools = _normalize_tools(result["tools"])
                            if tools:
                                return tools
                        if isinstance(result, list):
                            tools = _normalize_tools(result)
                            if tools:
                                return tools
            resp = await client.get(endpoint_url, headers={"Accept": "application/json"})
            if resp.is_success:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    data = resp.json()
                    tools = _normalize_tools(data)
                    if tools:
                        return tools
    except Exception:
        pass

    return []
