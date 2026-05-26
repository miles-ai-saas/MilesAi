"""流程运行 steps 审计条目（供调试面板与 LangGraph compiler 使用）。"""

from __future__ import annotations

from typing import Any


def build_flow_node_step(
    *,
    node_id: str,
    node_type: str,
    result: Any,
    engine: str = "langgraph",
) -> dict[str, Any]:
    """单节点执行结果 → step dict；生成物附带 ``artifact`` 供前端预览。"""
    step: dict[str, Any] = {
        "type": "flow_node",
        "engine": engine,
        "node_id": node_id,
        "node_type": node_type,
        "output_preview": str(result)[:200],
    }
    if not isinstance(result, dict):
        return step

    kind = result.get("kind")
    att = result.get("attachment_id")
    if kind in ("image", "video") and att:
        step["artifact"] = {
            "kind": kind,
            "attachment_id": str(att),
            "mime_type": result.get("mime_type"),
        }
        if kind == "image":
            extra_ids = result.get("attachment_ids")
            if isinstance(extra_ids, list) and len(extra_ids) > 1:
                mime = result.get("mime_type")
                step["artifacts"] = [
                    {
                        "kind": "image",
                        "attachment_id": str(aid),
                        "mime_type": mime,
                    }
                    for aid in extra_ids
                    if aid
                ]
    return step
