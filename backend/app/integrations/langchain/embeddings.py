"""LangChain Embeddings：知识库绑定 ModelConfig（model_type=embedding）。

向量维度须与 kb.embedding_dimension 一致；入库/检索均通过本模块按 KB 解析模型配置。
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
    """Celery 入库：按 KB 解析 embedding 模型并批量向量化分片。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_documents(texts)


def embed_query_for_kb_sync(db: Session, kb: KnowledgeBase, query: str) -> list[float]:
    """同步单条 query 向量化（脚本或同步检索路径）。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_query(query)


async def embed_texts_for_kb(
    db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, texts: list[str]
) -> list[list[float]]:
    """异步批量向量化（非入库主路径）。"""
    model = await resolve_embedding_model_by_id(
        db, kb.embedding_model_config_id, tenant_id
    )
    return build_embeddings(model).embed_documents(texts)


async def embed_query_for_kb(
    db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, query: str
) -> list[float]:
    """API 检索：将用户 query 转为与 KB 维度一致的向量。"""
    model = await resolve_embedding_model_by_id(
        db, kb.embedding_model_config_id, tenant_id
    )
    return build_embeddings(model).embed_query(query)


# 兼容旧名：同步入库路径
def embed_texts_for_kb_legacy(db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    """兼容旧 import，等同 embed_texts_for_kb_sync。"""
    return embed_texts_for_kb_sync(db, kb, texts)


PlatformEmbeddings = Embeddings
