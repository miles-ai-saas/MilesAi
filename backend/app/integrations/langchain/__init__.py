"""
LangChain 统一 AI 能力层（L3，惰性 ``__getattr__`` 导出）。

分层对应
--------
- embeddings：真实调用 embedding API（入库/检索 query）
- vectorstores：检索 → rag.retrieve
- chat_models：对话生成
- generate.*：简单 RAG 问答（re-export）

避免在业务代码中深层 import 未使用的子模块，缩短冷启动。
"""

__all__ = [
    "ainvoke_chat",
    "build_rag_user_prompt",
    "embed_query_for_kb",
    "embed_query_for_kb_sync",
    "embed_texts_for_kb",
    "embed_texts_for_kb_sync",
    "format_hits_context",
    "get_chat_model",
    "rag_answer",
    "retrieve_hits",
    "search_kb",
    "search_multi_kb_async",
    "split_text",
]


def __getattr__(name: str):
    if name in ("ainvoke_chat", "get_chat_model"):
        from app.integrations.langchain.chat_models import ainvoke_chat, get_chat_model

        return {"ainvoke_chat": ainvoke_chat, "get_chat_model": get_chat_model}[name]
    if name in (
        "embed_query_for_kb",
        "embed_query_for_kb_sync",
        "embed_texts_for_kb",
        "embed_texts_for_kb_sync",
    ):
        from app.integrations.langchain import embeddings as emb

        return getattr(emb, name)
    if name == "split_text":
        from app.rag.chunk import split_text

        return split_text
    if name in (
        "search_kb",
        "search_multi_kb_async",
    ):
        from app.integrations.langchain import vectorstores as vs

        return getattr(vs, name)
    if name in (
        "retrieve_hits",
        "format_hits_context",
        "build_rag_user_prompt",
        "rag_answer",
    ):
        from app.rag import generate as rag_gen

        return getattr(rag_gen, name)
    raise AttributeError(name)
