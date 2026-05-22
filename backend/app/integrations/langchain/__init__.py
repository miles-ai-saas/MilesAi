"""LangChain 统一 AI 能力层（惰性导出，避免 import 子模块时拉全链）。"""

__all__ = [
    "ainvoke_chat",
    "get_chat_model",
    "embed_query_for_kb",
    "embed_query_for_kb_sync",
    "embed_texts_for_kb",
    "embed_texts_for_kb_sync",
    "split_text",
    "search_kb",
    "search_multi_kb",
    "search_multi_kb_async",
    "search_as_documents",
    "retrieve_hits",
    "format_hits_context",
    "build_rag_user_prompt",
    "rag_answer",
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
        "search_multi_kb",
        "search_multi_kb_async",
        "search_as_documents",
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
