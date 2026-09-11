"""MCP 工具列表归一化（下沉自 tenant.mcp.client，供 Runner 复用）。"""

from __future__ import annotations


def normalize_tools(raw: list | dict) -> list[dict]:
    """将 tools/list 的多种返回形状统一为 ``[{name, description, inputSchema?, annotations?}]``。

    ``inputSchema`` / ``annotations`` 供智能体 function calling 构造参数 schema 与确认策略；
    旧缓存（无这两键）仍可解析，只是参数为空、默认需确认。
    """
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
            entry: dict = {"name": str(name), "description": str(desc)}
            schema = item.get("inputSchema") or item.get("input_schema")
            if isinstance(schema, dict):
                entry["inputSchema"] = schema
            annotations = item.get("annotations")
            if isinstance(annotations, dict):
                entry["annotations"] = annotations
            out.append(entry)
        elif isinstance(item, str):
            out.append({"name": item, "description": ""})
    return out
