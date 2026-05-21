"""文本向量化 — 委托 LangChain Embeddings 层。"""

from app.ai_stack.langchain.embeddings import embed_query, embed_texts, get_embeddings

__all__ = ["embed_query", "embed_texts", "get_embeddings"]
