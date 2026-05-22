"""RAG 上下文拼装。"""

from __future__ import annotations

from typing import Any


def format_hits_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    return "\n\n".join(
        f"[{h.get('score', 0):.2f}] {h.get('content_preview', '')}" for h in hits
    )


def build_rag_user_prompt(
    *,
    system_prompt: str,
    query: str,
    hits: list[dict[str, Any]],
) -> str:
    context = format_hits_context(hits)
    return f"{system_prompt}\n\n参考内容：\n{context}\n\n用户问题：{query}"
