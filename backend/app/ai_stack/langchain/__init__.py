"""LangChain 统一 AI 能力层。"""

from app.ai_stack.langchain.chat_models import ainvoke_chat, get_chat_model
from app.ai_stack.langchain.chunking import split_text
from app.ai_stack.langchain.embeddings import embed_query, embed_texts, get_embeddings
from app.ai_stack.langchain.rag import (
    build_rag_user_prompt,
    format_hits_context,
    rag_answer,
    retrieve_hits,
)
from app.ai_stack.langchain.vectorstores import search_as_documents, search_kb, search_multi_kb

__all__ = [
    "ainvoke_chat",
    "get_chat_model",
    "get_embeddings",
    "embed_query",
    "embed_texts",
    "split_text",
    "search_kb",
    "search_multi_kb",
    "search_as_documents",
    "retrieve_hits",
    "format_hits_context",
    "build_rag_user_prompt",
    "rag_answer",
]
