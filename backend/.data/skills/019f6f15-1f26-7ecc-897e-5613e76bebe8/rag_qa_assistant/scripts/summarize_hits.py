"""将 knowledge_search 返回的 hits 整理为简短摘要。"""


def run(params):
    hits = params.get("hits") or []
    if not isinstance(hits, list):
        return {"error": "hits 须为列表"}
    lines = []
    for i, h in enumerate(hits[:8], 1):
        if not isinstance(h, dict):
            continue
        title = h.get("title") or h.get("source") or f"片段{i}"
        snippet = str(h.get("content") or h.get("text") or "")[:240]
        lines.append(f"{i}. {title}: {snippet}")
    return {"summary": "\n".join(lines) if lines else "无检索结果"}
