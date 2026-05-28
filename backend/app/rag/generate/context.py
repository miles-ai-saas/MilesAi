"""
RAG 上下文拼装：将检索 hit 格式化为 LLM 可读的参考片段。

hit 字段来自 ``integrations.langchain.vector.documents._doc_to_hit_row``；
``content_preview`` 多为向量库写入时的截断预览，可能短于 PG ``DocumentChunk.content`` 全文。
"""

from __future__ import annotations

from typing import Any


def format_hits_context(hits: list[dict[str, Any]]) -> str:
    """
    将多条 hit 拼成「参考内容」段落。

    每行格式：``[score] content_preview``，供 ``build_rag_user_prompt`` 嵌入 user 消息。
    """
    if not hits:
        return ""
    return "\n\n".join(f"[{h.get('score', 0):.2f}] {h.get('content_preview', '')}" for h in hits)


def build_rag_user_prompt(
    *,
    system_prompt: str,
    query: str,
    hits: list[dict[str, Any]],
) -> str:
    """
    组装单次 RAG 对话的用户侧 prompt（非 Chat API 的 system role 分离）。

    结构：system 指令 + 参考内容 + 用户问题；无 hit 时由 ``answer.rag_answer`` 仅用 system+问题。
    """
    context = format_hits_context(hits)
    return f"{system_prompt}\n\n参考内容：\n{context}\n\n用户问题：{query}"
