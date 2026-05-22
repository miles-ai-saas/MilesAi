"""LangChain Embeddings：知识库绑定 ModelConfig（model_type=embedding）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.embeddings import Embeddings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.ai_stack.embeddings.runtime import build_embeddings
from app.tenant.models.services.embedding_resolve import (
    resolve_embedding_model_by_id,
    resolve_embedding_model_sync,
)

if TYPE_CHECKING:
    from app.models.kb import KnowledgeBase


def embed_texts_for_kb_sync(db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_documents(texts)


def embed_query_for_kb_sync(db: Session, kb: KnowledgeBase, query: str) -> list[float]:
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_query(query)


async def embed_texts_for_kb(
    db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, texts: list[str]
) -> list[list[float]]:
    model = await resolve_embedding_model_by_id(
        db, kb.embedding_model_config_id, tenant_id
    )
    return build_embeddings(model).embed_documents(texts)


async def embed_query_for_kb(
    db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, query: str
) -> list[float]:
    model = await resolve_embedding_model_by_id(
        db, kb.embedding_model_config_id, tenant_id
    )
    return build_embeddings(model).embed_query(query)


# 兼容旧名：同步入库路径
def embed_texts_for_kb_legacy(db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    return embed_texts_for_kb_sync(db, kb, texts)


PlatformEmbeddings = Embeddings
