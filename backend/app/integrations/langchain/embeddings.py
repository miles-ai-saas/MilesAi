"""
LangChain Embeddings 适配：按知识库绑定的 ModelConfig 调用远程 embedding API。

与 PrecomputedEmbeddings 的区别
------------------------------
- **本模块**：入库/检索时**真正调用** embedding 模型（``build_embeddings`` → LiteLLM 等）。
- **PrecomputedEmbeddings**（infra.vector_store）：向量已算好，仅满足 LangChain VectorStore API 形状。

维度
----
须与 ``KnowledgeBase.embedding_dimension`` 一致（创建 KB 时固化）；切换模型需新建 KB。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.embeddings import Embeddings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.integrations.embeddings.runtime import build_embeddings
from app.tenant.models.services.embedding_resolve import (
    resolve_embedding_model_by_id,
    resolve_embedding_model_sync,
)

if TYPE_CHECKING:
    from app.models.kb import KnowledgeBase


def embed_texts_for_kb_sync(db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    """Celery 入库 pipeline 注入：批量 embed 分片文本。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_documents(texts)


def embed_query_for_kb_sync(db: Session, kb: KnowledgeBase, query: str) -> list[float]:
    """同步检索路径（脚本或多 KB sync）。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_query(query)


async def embed_texts_for_kb(db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    """异步批量 embed（非入库主路径）。"""
    model = await resolve_embedding_model_by_id(db, kb.embedding_model_config_id, tenant_id)
    return build_embeddings(model).embed_documents(texts)


async def embed_query_for_kb(db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, query: str) -> list[float]:
    """HTTP API 检索、Agent async 检索：query → 与 KB 同维度的向量。"""
    model = await resolve_embedding_model_by_id(db, kb.embedding_model_config_id, tenant_id)
    return build_embeddings(model).embed_query(query)


PlatformEmbeddings = Embeddings
