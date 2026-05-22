"""向量化门面：知识库须绑定 ModelConfig，请使用 embed_*_for_kb。"""

from app.ai_stack.langchain.embeddings import (
    embed_query_for_kb_sync,
    embed_texts_for_kb_sync,
)

__all__ = ["embed_query_for_kb_sync", "embed_texts_for_kb_sync"]
